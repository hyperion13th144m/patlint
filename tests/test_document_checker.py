from __future__ import annotations

import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text
from patent_document_checker.parser import RawBlock, extract_claim_references, parse_text
from patent_document_checker.structured_parser import parse_blocks_to_tree


class DocumentCheckerTests(unittest.TestCase):
    def test_extracts_claims_with_fullwidth_numbers(self) -> None:
        document = parse_text("【特許請求の範囲】\n【請求項１】装置。\n【請求項２】請求項１に記載の装置。")

        self.assertEqual([claim.number for claim in document.claims], [1, 2])
        self.assertEqual(document.claims[1].referenced_claims, [1])

    def test_reports_forbidden_characters_as_errors(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【０００１】第①部材は半角ｶﾅと合成用丸⃝と髙さを含む。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "FORBIDDEN_CHARACTER"
        ]

        self.assertEqual([diagnostic.severity for diagnostic in diagnostics], ["error"] * 5)
        self.assertEqual(
            [diagnostic.location.search_text for diagnostic in diagnostics],
            ["①", "ｶ", "ﾅ", "⃝", "髙"],
        )
        self.assertEqual(
            [diagnostic.message for diagnostic in diagnostics],
            [
                "使用できない文字 ① が含まれています（丸付数字、位置: 8文字目）。",
                "使用できない文字 ｶ が含まれています（半角カナ、位置: 14文字目）。",
                "使用できない文字 ﾅ が含まれています（半角カナ、位置: 15文字目）。",
                "使用できない文字 ⃝ が含まれています（合成用丸、位置: 21文字目）。",
                "使用できない文字 髙 が含まれています（Shift_JISに変換できない文字、位置: 23文字目）。",
            ],
        )

    def test_allows_jis_x0208_shift_jis_characters_and_ascii_space(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【０００１】ASCII text と漢字、ひらがな、カタカナ、記号○～－∥￢を含む。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "FORBIDDEN_CHARACTER"
                for diagnostic in result.diagnostics
            )
        )

    def test_reports_missing_duplicate_self_and_future_references(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項3】請求項3に記載の装置。",
                    "【請求項3】請求項4に記載の装置。",
                ]
            )
        )

        messages = [diagnostic.message for diagnostic in result.diagnostics]
        self.assertIn("請求項2が欠落しています。", messages)
        self.assertIn("請求項3が重複しています。", messages)
        self.assertIn("請求項3が自己引用しています。", messages)
        self.assertIn("請求項3が存在しない請求項4を引用しています。", messages)

    def test_reports_multi_multi_claim(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項2又は3に記載の装置。",
                ]
            )
        )

        self.assertTrue(any(diagnostic.rule_id == "MULTI_MULTI_CLAIM" for diagnostic in result.diagnostics))

    def test_claims_track_official_multi_multi_states(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項2又は3に記載の装置。",
                    "【請求項5】請求項4に記載の装置。",
                    "【請求項6】請求項5に記載の装置。",
                ]
            )
        )

        states = {
            claim.number: (
                claim.is_multiple_dependent,
                claim.references_multiple_dependent,
                claim.is_multi_multi,
                claim.references_multi_multi,
            )
            for claim in document.claims
        }
        self.assertEqual(states[3], (True, False, False, False))
        self.assertEqual(states[4], (True, True, True, False))
        self.assertEqual(states[5], (False, True, False, True))
        self.assertEqual(states[6], (False, True, False, True))

    def test_reports_indirect_official_multi_multi_claim(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】請求項1に記載の装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項3に記載の装置。",
                    "【請求項5】請求項2又は4に記載の装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "MULTI_MULTI_CLAIM"
        ]
        self.assertEqual(messages, ["請求項5がマルチマルチクレームとして検出されました。"])

    def test_extract_claim_references_supports_ranges(self) -> None:
        self.assertEqual(extract_claim_references("請求項１〜３のいずれかに記載の装置。"), [1, 2, 3])
        self.assertEqual(extract_claim_references("請求項4から2のいずれかに記載の装置。"), [4, 3, 2])

    def test_extract_claim_references_supports_omitted_claim_prefixes(self) -> None:
        self.assertEqual(extract_claim_references("請求項１、２、４に記載の装置。"), [1, 2, 4])
        self.assertEqual(extract_claim_references("請求項１を引用する請求項３に記載の装置。"), [1, 3])
        self.assertEqual(extract_claim_references("請求項１を引用する請求項４、６～８に記載の装置。"), [1, 4, 6, 7, 8])

    def test_reports_missing_paragraph_number_after_last_valid_number(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文。",
                    "【０００２】本文。",
                    "【０００４】本文。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "PARAGRAPH_NUMBERING"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(
            diagnostics[0].message,
            "段落番号は2まで正しく連番ですが、それ以降は連番ではありません。",
        )
        self.assertEqual(diagnostics[0].location.search_text, "【0004】")

    def test_allows_sequential_paragraph_numbers(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文。",
                    "【０００２】本文。",
                    "【０００３】本文。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "PARAGRAPH_NUMBERING"
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_dictionary_term_repeated_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】前記流路は、それぞれよりも小さな絞り部を有し、前記絞り部の周囲には、冷却流路が形成されている装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_repeated_claim_term_lacks_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔は、前記アルミ箔を支持し、アルミ箔の端部を覆う装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "請求項1の語句 アルミ箔 は、2回目以降または引用元の請求項で出現済みですが、前記・該・当該が付いていません（前記ぬけ）。",
        )

    def test_allows_repeated_claim_term_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔は、前記アルミ箔を支持し、当該アルミ箔の端部を覆う装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_at_end(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】前記流路部材が、酸化アルミニウムからなる、ことを特徴とする請求項1に記載のパルス殺菌器処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_at_start(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌器処理槽において、前記流路部材が酸化アルミニウムからなる装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_multiple_claim_reference(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌器処理槽。",
                    "【請求項3】請求項1または請求項2に記載のパルス殺菌器処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_with_variant_phrases(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌処理槽。",
                    "【請求項3】請求項1に記載するパルス殺菌処理槽。",
                    "【請求項4】請求項1に記載されたパルス殺菌処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_dependent_claim_term_lacks_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔を備える装置。",
                    "【請求項2】請求項1に記載の装置であって、アルミ箔が樹脂層に接する装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
        ]
        self.assertIn(
            "請求項2の語句 アルミ箔 は、2回目以降または引用元の請求項で出現済みですが、前記・該・当該が付いていません（前記ぬけ）。",
            messages,
        )

    def test_allows_dependent_claim_term_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔を備える装置。",
                    "【請求項2】請求項1に記載の装置であって、前記アルミ箔が樹脂層に接する装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_for_term_variations_with_same_suffix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】一端側１０と他端側２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】一端側と他端側を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertIn(
            "語句 一端側 と 他端側 は、末尾「端側」が一致していますが先頭が異なります。",
            messages,
        )

    def test_warns_for_term_variations_with_same_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】アルミ箔１０とアルミ製２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】アルミ箔とアルミ製を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertIn(
            "語句 アルミ箔 と アルミ製 は、先頭「アルミ」が一致していますが末尾が異なります。",
            messages,
        )

    def test_ignores_term_variations_with_long_unmatched_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス殺菌器処理槽１０と処理槽２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス殺菌器処理槽と処理槽を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertNotIn(
            "語句 パルス殺菌器処理槽 と 処理槽 は、末尾「処理槽」が一致していますが先頭が異なります。",
            messages,
        )

    def test_warns_when_same_term_has_different_signs(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部６は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_SIGN_CONFLICT"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "符号付語句 パルス印加部 は、複数の符号で記載されています（5: 0001, 要約書、6: 0002）。",
        )

    def test_allows_same_term_with_same_sign_in_multiple_locations(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "TERM_SIGN_CONFLICT"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_same_sign_has_different_terms(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】制御部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "SIGN_TERM_CONFLICT"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "符号 5 は、複数の語句で記載されています（パルス印加部: 0001, 要約書、制御部: 0002）。",
        )

    def test_allows_same_sign_with_same_term_in_multiple_locations(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "SIGN_TERM_CONFLICT"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_for_long_sentence_in_embodiments(self) -> None:
        long_sentence = "あ" * 199 + "。"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    f"【０００１】{long_sentence}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(diagnostics[0].message, "実施形態の一文が長すぎます（200文字）。")
        self.assertEqual(diagnostics[0].location.search_text, "【0001】")

    def test_allows_short_sentences_and_ignores_non_embodiment_long_sentences(self) -> None:
        long_sentence = "あ" * 199 + "。"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【背景技術】",
                    f"【０００１】{long_sentence}",
                    "【発明を実施するための形態】",
                    f"【０００２】{'い' * 198}。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_for_fullwidth_period_long_sentence_in_embodiments(self) -> None:
        long_sentence = "あ" * 199 + "．"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    f"【０００１】短文。{long_sentence}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].message, "実施形態の一文が長すぎます（200文字）。")

    def test_warns_when_claim_term_is_missing_from_embodiments(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_IN_EMBODIMENTS"
        ]
        self.assertIn("請求項の語句 CPUモジュールは、実施形態に記載されていません", messages)
        self.assertNotIn("請求項の語句 制御部は、実施形態に記載されていません", messages)

    def test_allows_claim_terms_found_in_embodiments(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】CPUモジュールと制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_IN_EMBODIMENTS"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_claim_term_is_missing_from_tech_solution(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の概要】",
                    "【課題を解決するための手段】",
                    "【０００１】制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_IN_TECH_SOLUTION"
        ]
        self.assertIn("請求項の語句 CPUモジュールは、解決手段に記載されていません", messages)
        self.assertNotIn("請求項の語句 制御部は、解決手段に記載されていません", messages)

    def test_allows_claim_terms_found_in_tech_solution(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の概要】",
                    "【課題を解決するための手段】",
                    "【０００１】CPUモジュールと制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_IN_TECH_SOLUTION"
                for diagnostic in result.diagnostics
            )
        )

    def test_builds_tagged_document_tree(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の名称】ハンドスキャナ",
                    "【技術分野】",
                    "【０００１】",
                    "本発明は、走査位置の観測確認が容易なハンドスキャナに関する。",
                    "【図面の簡単な説明】",
                    "【０００２】",
                    "【図１】ハンドスキャナの説明図である。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                    "【請求項２】請求項１に記載の装置。",
                ]
            )
        )

        tree = document.tree
        self.assertIsNotNone(tree)
        documents = tree.find_all(kind="document")
        self.assertEqual([node.text for node in documents], ["明細書", "特許請求の範囲"])
        spec = documents[0]
        self.assertEqual(spec.children[0].tag_name, "発明の名称")
        self.assertEqual(spec.children[1].children[0].tag_name, "0001")
        claim_doc = documents[1]
        self.assertEqual([node.number for node in claim_doc.find_all(kind="claim")], [1, 2])

    def test_tree_handles_multiple_tags_on_one_line(self) -> None:
        tree = parse_blocks_to_tree([RawBlock(id="b0", index=0, text="【００１１】【図１】説明図。【図２】別の説明図。")])

        paragraph = tree.find_all(kind="paragraph")[0]
        figures = paragraph.find_all(kind="figure")
        self.assertEqual([figure.number for figure in figures], [1, 2])
        self.assertEqual(figures[0].text, "説明図。")



if __name__ == "__main__":
    unittest.main()
