from agent_replay.ir import ExecutionGraph, EdgeKind
from .ir_compiler import REPLAY_POINT_KINDS
from .plan import ReplaySession, ReplayPlan, Instruction, InstructionKind

class PlanCompiler:
    """
    Merges an ExecutionGraph with a ReplaySession to produce a side-effect-free ReplayPlan.
    """
    def compile(self, graph: ExecutionGraph, session: ReplaySession) -> ReplayPlan:
        instructions = []

        # 1. Topological Traversal (MVP: Find the root node, then follow the edges)
        # Only SEQUENTIAL edges describe replay order; PARENT_CHILD edges are structure.
        sequential = [e for e in graph.edges.values() if e.kind == EdgeKind.SEQUENTIAL]
        next_of = {e.source: e.target for e in sequential}
        target_nodes = {e.target for e in sequential}
        roots = [
            node_id for node_id, node in graph.nodes.items()
            if node_id not in target_nodes and node.kind in REPLAY_POINT_KINDS and node.metadata.replayable
        ]

        if not roots:
            return ReplayPlan(graph_id=graph.id, instructions=[])

        current_node_id = roots[0]

        # 2. Linearize into Instructions
        while current_node_id:
            node = graph.nodes[current_node_id]

            # For the MVP, we only support CACHE mode (Deterministic Replay)
            if session.mode == "CACHE":
                instruction = Instruction(
                    kind=InstructionKind.RETURN_RECORDED,
                    node_id=node.id,
                    expected_input=node.input,
                    output_to_return=node.output,
                    node_kind=node.kind,
                )
                instructions.append(instruction)

            # Find the next node via edges
            current_node_id = next_of.get(current_node_id)

        return ReplayPlan(graph_id=graph.id, instructions=instructions)
