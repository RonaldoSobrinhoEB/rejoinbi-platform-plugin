import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "rejoinbi"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_cli", SCRIPT_PATH)
rejoinbi = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(rejoinbi)


class PageHierarchyTests(unittest.TestCase):
    def test_set_page_order_uses_backend_canonical_fields(self):
        class FakeClient:
            def __init__(self):
                self.request_payload = None

            def request(self, method, path, **kwargs):
                self.request_payload = {
                    "method": method,
                    "path": path,
                    "json": kwargs.get("json"),
                }
                return {"success": True}, None

        client = FakeClient()
        args = SimpleNamespace(
            data_file=None,
            data_json=None,
            page_id="neto",
            position=2,
            parent="filho",
            before=None,
            after=None,
            json=True,
        )
        pages = [
            {"id": "pai", "nome": "Pai", "pai": ""},
            {"id": "filho", "nome": "Filho", "pai": "pai"},
            {"id": "neto", "nome": "Neto", "pai": "pai"},
        ]
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "list_pages", return_value=pages),
            patch.object(rejoinbi, "refresh_menu_caches", return_value=[]),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_set_page_order(args), 0)

        self.assertEqual(client.request_payload["method"], "PUT")
        self.assertEqual(client.request_payload["path"], "/plataforma/api/paginas/neto/ordem")
        self.assertEqual(
            client.request_payload["json"],
            {"ordem_menu": 2, "pai": "filho"},
        )

    def test_nested_manifest_flattens_parent_first_through_grandchild(self):
        pages = rejoinbi.prepare_manifest_pages([
            {
                "id": "pai",
                "name": "Pai",
                "children": [
                    {
                        "id": "filho",
                        "name": "Filho",
                        "children": [
                            {"id": "neto", "name": "Neto"},
                        ],
                    },
                ],
            },
        ])

        self.assertEqual([page["id"] for page in pages], ["pai", "filho", "neto"])
        self.assertEqual(pages[1]["parent"], "pai")
        self.assertEqual(pages[2]["parent"], "filho")
        summary = rejoinbi.manifest_hierarchy_summary(pages)
        self.assertEqual(summary["max_depth"], 2)
        self.assertTrue(summary["recursive_depth_supported"])

    def test_flat_manifest_is_topologically_sorted(self):
        pages = rejoinbi.prepare_manifest_pages([
            {"id": "neto", "name": "Neto", "parent": "filho"},
            {"id": "pai", "name": "Pai"},
            {"id": "filho", "name": "Filho", "parent": "pai"},
        ])
        self.assertEqual([page["id"] for page in pages], ["pai", "filho", "neto"])

    def test_manifest_cycle_is_blocked(self):
        with self.assertRaisesRegex(rejoinbi.RejoinBIError, "cycle"):
            rejoinbi.prepare_manifest_pages([
                {"id": "pai", "name": "Pai", "parent": "filho"},
                {"id": "filho", "name": "Filho", "parent": "pai"},
            ])

    def test_parent_resolver_allows_grandchild_and_blocks_cycle(self):
        pages = [
            {"id": "pai", "nome": "Pai", "pai": ""},
            {"id": "filho", "nome": "Filho", "pai": "pai"},
            {"id": "neto", "nome": "Neto", "pai": "filho"},
        ]
        self.assertEqual(rejoinbi.resolve_page_parent_id(pages, "filho"), "filho")
        with self.assertRaisesRegex(rejoinbi.RejoinBIError, "cycle"):
            rejoinbi.resolve_page_parent_id(pages, "neto", child_id="pai")

    def test_accessible_tree_keeps_inferred_parent_and_depth(self):
        flat = rejoinbi.flatten_page_tree({
            "pages": [
                {
                    "id": "pai",
                    "subpaginas": [
                        {
                            "id": "filho",
                            "subpaginas": [{"id": "neto"}],
                        },
                    ],
                },
            ],
        })
        by_id = {page["id"]: page for page in flat}
        self.assertEqual(by_id["filho"]["_tree_parent_id"], "pai")
        self.assertEqual(by_id["neto"]["_tree_parent_id"], "filho")
        self.assertEqual(by_id["neto"]["_tree_depth"], 2)

    def test_portuguese_display_name_accents_are_not_corrupted(self):
        self.assertEqual(
            rejoinbi.suggest_pt_br_display_name("Visao Geral"),
            "Vis\u00e3o Geral",
        )
        self.assertEqual(
            rejoinbi.suggest_pt_br_display_name("Vis\u00e3o Geral"),
            "Vis\u00e3o Geral",
        )
        self.assertFalse(rejoinbi.looks_like_corrupted_text("Vis\u00e3o Geral"))


if __name__ == "__main__":
    unittest.main()
