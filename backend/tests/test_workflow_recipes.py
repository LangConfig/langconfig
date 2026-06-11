# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Structural validation for the out-of-box workflow recipe templates.

Every recipe must be executable by core/workflows/executor.py as-is, so these
tests assert the executor's actual contracts:
- top-level node ``type`` + top-level ``config`` (DB/executor format)
- conditional routing via routing_map values matching outgoing edge data.label
- loop nodes with continue/exit labeled edges and a max_iterations cap
- critic nodes named so the executor captures state.critic_output
- deferred flags only on fan-in nodes
- only real native tools and real models
"""

import pytest

from constants.models import ModelChoice
from core.templates.workflow_recipes import (
    WORKFLOW_RECIPES,
    get_all_recipes,
    get_recipe_by_id,
    recipe_to_dict,
)
from tools.native_tools import TOOL_NAME_MAP

VALID_MODELS = {m.value for m in ModelChoice}

CONTROL_TYPES = {
    "START_NODE", "END_NODE", "OUTPUT_NODE", "CHECKPOINT_NODE",
    "CONDITIONAL_NODE", "APPROVAL_NODE", "LOOP_NODE",
}

AGENT_REQUIRED_CONFIG_FIELDS = {
    "model", "temperature", "system_prompt", "native_tools", "tools",
    "cli_tools", "custom_tools", "timeout_seconds", "max_retries",
    "enable_model_routing", "enable_parallel_tools", "enable_memory",
    "fallback_models",
}

ALLOWED_CATEGORIES = {"research", "coding", "privacy", "content", "code-review"}


def _node_type(node):
    return node.get("type") or node.get("data", {}).get("agentType")


def _agent_nodes(recipe):
    return [
        n for n in recipe.nodes
        if _node_type(n) not in CONTROL_TYPES and _node_type(n) != "TOOL_NODE"
    ]


def _nodes_by_id(recipe):
    return {n["id"]: n for n in recipe.nodes}


@pytest.fixture(params=WORKFLOW_RECIPES, ids=lambda r: r.recipe_id)
def recipe(request):
    return request.param


class TestRegistry:
    def test_eight_recipes_registered(self):
        assert len(get_all_recipes()) == 8

    def test_recipe_ids_unique(self):
        ids = [r.recipe_id for r in WORKFLOW_RECIPES]
        assert len(ids) == len(set(ids))

    def test_recipe_names_unique(self):
        names = [r.name for r in WORKFLOW_RECIPES]
        assert len(names) == len(set(names))

    def test_get_recipe_by_id_roundtrip(self):
        for r in WORKFLOW_RECIPES:
            assert get_recipe_by_id(r.recipe_id) is r
        with pytest.raises(KeyError):
            get_recipe_by_id("does_not_exist")


class TestMetadata:
    def test_metadata_complete(self, recipe):
        assert recipe.name.strip()
        assert recipe.description.strip()
        assert recipe.icon.strip()
        assert recipe.tags, f"{recipe.recipe_id} has no tags"
        assert recipe.category in ALLOWED_CATEGORIES

    def test_recipe_to_dict_canvas_shape(self, recipe):
        d = recipe_to_dict(recipe)
        assert d["node_count"] == len(recipe.nodes)
        assert d["edge_count"] == len(recipe.edges)
        # Canvas-insert API must expose ReactFlow's "custom" node type while
        # preserving the semantic type in data.agentType.
        for node in d["nodes"]:
            assert node["type"] == "custom"
            assert node["data"]["agentType"]


class TestGraphStructure:
    def test_unique_node_ids(self, recipe):
        ids = [n["id"] for n in recipe.nodes]
        assert len(ids) == len(set(ids)), f"duplicate node ids in {recipe.recipe_id}"

    def test_unique_edge_ids(self, recipe):
        ids = [e["id"] for e in recipe.edges]
        assert len(ids) == len(set(ids)), f"duplicate edge ids in {recipe.recipe_id}"

    def test_edges_reference_existing_nodes(self, recipe):
        node_ids = {n["id"] for n in recipe.nodes}
        for edge in recipe.edges:
            assert edge["source"] in node_ids, f"{recipe.recipe_id}: {edge['id']} bad source"
            assert edge["target"] in node_ids, f"{recipe.recipe_id}: {edge['id']} bad target"

    def test_has_start_end_and_output_framing(self, recipe):
        types = [_node_type(n) for n in recipe.nodes]
        assert "START_NODE" in types, f"{recipe.recipe_id} missing START_NODE"
        assert "END_NODE" in types, f"{recipe.recipe_id} missing END_NODE"
        assert "OUTPUT_NODE" in types, f"{recipe.recipe_id} missing OUTPUT_NODE (observability)"

    def test_output_node_feeds_end(self, recipe):
        nodes = _nodes_by_id(recipe)
        output_ids = {nid for nid, n in nodes.items() if _node_type(n) == "OUTPUT_NODE"}
        end_ids = {nid for nid, n in nodes.items() if _node_type(n) == "END_NODE"}
        for oid in output_ids:
            targets = {e["target"] for e in recipe.edges if e["source"] == oid}
            assert targets & end_ids, f"{recipe.recipe_id}: OUTPUT_NODE {oid} does not reach END_NODE"

    def test_every_non_terminal_node_has_outgoing_edge(self, recipe):
        sources = {e["source"] for e in recipe.edges}
        for node in recipe.nodes:
            if _node_type(node) == "END_NODE":
                continue
            assert node["id"] in sources, (
                f"{recipe.recipe_id}: node {node['id']} has no outgoing edge"
            )

    def test_positions_present_on_clean_grid(self, recipe):
        for node in recipe.nodes:
            pos = node.get("position")
            assert pos and isinstance(pos["x"], (int, float)) and isinstance(pos["y"], (int, float)), (
                f"{recipe.recipe_id}: node {node['id']} missing position"
            )
            assert 0 <= pos["x"] <= 1650, f"{recipe.recipe_id}: {node['id']} x out of range"
            assert 0 <= pos["y"] <= 600, f"{recipe.recipe_id}: {node['id']} y out of range"

    def test_no_overlapping_positions(self, recipe):
        seen = {}
        for node in recipe.nodes:
            key = (node["position"]["x"], node["position"]["y"])
            assert key not in seen, (
                f"{recipe.recipe_id}: nodes {seen[key]} and {node['id']} overlap at {key}"
            )
            seen[key] = node["id"]


class TestNodeConfig:
    def test_executor_format_top_level_type_and_config(self, recipe):
        """Executor reads node['type'] and node['config'] - both must exist."""
        for node in recipe.nodes:
            assert node.get("type") not in (None, "", "default", "custom"), (
                f"{recipe.recipe_id}: node {node['id']} top-level type must be the "
                f"semantic agent type for the executor, got {node.get('type')!r}"
            )
            assert isinstance(node.get("config"), dict) and node["config"], (
                f"{recipe.recipe_id}: node {node['id']} missing top-level config"
            )
            # Canvas mirror must match
            assert node["data"]["agentType"] == node["type"]
            assert node["data"]["config"] == node["config"]

    def test_every_node_has_label(self, recipe):
        for node in recipe.nodes:
            assert node["data"].get("label", "").strip(), (
                f"{recipe.recipe_id}: node {node['id']} missing label"
            )

    def test_agent_nodes_have_full_config(self, recipe):
        for node in _agent_nodes(recipe):
            config = node["config"]
            missing = AGENT_REQUIRED_CONFIG_FIELDS - set(config)
            assert not missing, (
                f"{recipe.recipe_id}: agent node {node['id']} missing config fields {missing}"
            )
            assert config["system_prompt"].strip(), f"{node['id']} empty system_prompt"
            assert 120 <= config["timeout_seconds"] <= 600, f"{node['id']} timeout out of range"
            assert config["max_retries"] >= 1, f"{node['id']} max_retries"

    def test_agent_models_valid(self, recipe):
        for node in _agent_nodes(recipe):
            config = node["config"]
            assert config["model"] in VALID_MODELS, (
                f"{recipe.recipe_id}: {node['id']} model {config['model']!r} not in ModelChoice"
            )
            for fb in config.get("fallback_models", []):
                assert fb in VALID_MODELS, (
                    f"{recipe.recipe_id}: {node['id']} fallback {fb!r} not in ModelChoice"
                )

    def test_agent_nodes_have_fallback_models(self, recipe):
        for node in _agent_nodes(recipe):
            assert node["config"]["fallback_models"], (
                f"{recipe.recipe_id}: {node['id']} has no fallback_models"
            )

    def test_native_tools_exist(self, recipe):
        for node in recipe.nodes:
            for tool in node["config"].get("native_tools", []):
                assert tool in TOOL_NAME_MAP, (
                    f"{recipe.recipe_id}: {node['id']} references unknown native tool {tool!r}"
                )


class TestToolNodes:
    def test_tool_node_config(self, recipe):
        for node in recipe.nodes:
            if _node_type(node) != "TOOL_NODE":
                continue
            config = node["config"]
            assert config.get("tool_type") == "mcp", (
                f"{node['id']}: native tools load via tool_type 'mcp'"
            )
            assert config.get("tool_id") in TOOL_NAME_MAP, (
                f"{node['id']}: tool_id {config.get('tool_id')!r} not a native tool"
            )
            assert isinstance(config.get("tool_params"), dict) and config["tool_params"], (
                f"{node['id']}: tool_params missing"
            )


class TestConditionalRouting:
    def test_conditional_nodes_route_via_edge_labels(self, recipe):
        """routing_map values must match outgoing edge data.label values -
        the executor's router resolves conditional_route against edge labels."""
        for node in recipe.nodes:
            if _node_type(node) != "CONDITIONAL_NODE":
                continue
            config = node["config"]
            # Executor reads config['condition'] (NOT condition_expression)
            assert config.get("condition", "").strip(), (
                f"{node['id']}: missing 'condition' expression"
            )
            routing_map = config.get("routing_map", {})
            assert "true" in routing_map and "false" in routing_map, (
                f"{node['id']}: routing_map needs 'true' and 'false' keys"
            )

            out_edge_labels = {
                e.get("data", {}).get("label")
                for e in recipe.edges
                if e["source"] == node["id"]
            }
            for key in ("true", "false"):
                assert routing_map[key] in out_edge_labels, (
                    f"{recipe.recipe_id}: {node['id']} routing_map['{key}'] = "
                    f"{routing_map[key]!r} has no matching outgoing edge data.label "
                    f"(labels: {out_edge_labels})"
                )

    def test_critic_conditions_have_upstream_critic_node(self, recipe):
        """If a condition inspects state.critic_output, some agent node must be
        named/typed with 'critic' so the executor actually captures it."""
        for node in recipe.nodes:
            if _node_type(node) != "CONDITIONAL_NODE":
                continue
            if "critic_output" not in node["config"].get("condition", ""):
                continue
            critic_nodes = [
                n for n in recipe.nodes
                if "critic" in n["data"].get("label", "").lower()
                or "critic" in (_node_type(n) or "").lower()
            ]
            assert critic_nodes, (
                f"{recipe.recipe_id}: {node['id']} conditions on critic_output but no "
                f"node label/type contains 'critic'"
            )

    def test_critic_prompts_carry_verdict_contract(self, recipe):
        for node in recipe.nodes:
            ntype = (_node_type(node) or "").lower()
            label = node["data"].get("label", "").lower()
            if ntype in {t.lower() for t in CONTROL_TYPES} or ntype == "tool_node":
                continue
            if "critic" in label or "critic" in ntype:
                prompt = node["config"]["system_prompt"]
                assert "VERDICT: PASS" in prompt and "VERDICT: REVISE" in prompt, (
                    f"{recipe.recipe_id}: critic {node['id']} prompt missing verdict contract"
                )


class TestLoopNodes:
    def test_loop_nodes_have_continue_and_exit_edges(self, recipe):
        for node in recipe.nodes:
            if _node_type(node) != "LOOP_NODE":
                continue
            config = node["config"]
            assert isinstance(config.get("max_iterations"), int) and 1 <= config["max_iterations"] <= 5, (
                f"{node['id']}: max_iterations must cap the loop"
            )
            labels = {
                e.get("data", {}).get("label")
                for e in recipe.edges
                if e["source"] == node["id"]
            }
            assert labels == {"continue", "exit"}, (
                f"{recipe.recipe_id}: {node['id']} loop edges must be labeled "
                f"continue/exit, got {labels}"
            )

    def test_loop_continue_edge_creates_cycle(self, recipe):
        """The continue edge must point backward to an agent node (the loop body)."""
        nodes = _nodes_by_id(recipe)
        for node in recipe.nodes:
            if _node_type(node) != "LOOP_NODE":
                continue
            continue_edges = [
                e for e in recipe.edges
                if e["source"] == node["id"] and e.get("data", {}).get("label") == "continue"
            ]
            assert len(continue_edges) == 1
            target = nodes[continue_edges[0]["target"]]
            assert _node_type(target) not in CONTROL_TYPES, (
                f"{recipe.recipe_id}: loop continue edge should target an agent node"
            )


class TestDeferredNodes:
    def test_deferred_only_on_fan_in_nodes(self, recipe):
        """config.deferred=True is only valid on nodes with 2+ incoming edges
        (the whole point is waiting for parallel branches)."""
        in_degree = {}
        for edge in recipe.edges:
            in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1
        for node in recipe.nodes:
            if node["config"].get("deferred"):
                assert in_degree.get(node["id"], 0) >= 2, (
                    f"{recipe.recipe_id}: {node['id']} is deferred but has "
                    f"{in_degree.get(node['id'], 0)} incoming edges"
                )

    def test_fan_in_agent_nodes_are_deferred(self, recipe):
        """Agent nodes receiving multiple PARALLEL branches must defer, or they
        execute once per completed branch. Edges out of CONDITIONAL/LOOP nodes
        are alternative (mutually exclusive) paths, not parallel branches, so
        they do not count toward fan-in."""
        nodes = _nodes_by_id(recipe)
        in_degree = {}
        for edge in recipe.edges:
            source_type = _node_type(nodes[edge["source"]])
            if source_type in ("CONDITIONAL_NODE", "LOOP_NODE"):
                continue
            in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1
        for node in _agent_nodes(recipe):
            if in_degree.get(node["id"], 0) >= 2:
                assert node["config"].get("deferred") is True, (
                    f"{recipe.recipe_id}: fan-in agent node {node['id']} should set deferred=True"
                )
