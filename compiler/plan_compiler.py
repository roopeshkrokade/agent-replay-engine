from ir import ExecutionGraph
from .plan import ReplaySession, ReplayPlan, Instruction, InstructionKind

class PlanCompiler:
    """
    Merges an ExecutionGraph with a ReplaySession to produce a side-effect-free ReplayPlan.
    """
    def compile(self, graph: ExecutionGraph, session: ReplaySession) -> ReplayPlan:
        instructions = []
        
        # 1. Topological Traversal (MVP: Find the root node, then follow the edges)
        # In a DAG, a root has no incoming edges.
        target_nodes = {edge.target for edge in graph.edges.values()}
        roots = [node_id for node_id in graph.nodes.keys() if node_id not in target_nodes]
        
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
                    output_to_return=node.output
                )
                instructions.append(instruction)
            
            # Find the next node via edges
            next_edge = next((e for e in graph.edges.values() if e.source == current_node_id), None)
            current_node_id = next_edge.target if next_edge else None
            
        return ReplayPlan(graph_id=graph.id, instructions=instructions)