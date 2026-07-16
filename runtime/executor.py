from typing import Any
from compiler import Instruction, InstructionKind

class InstructionExecutor:
    """Blindly executes a terminal instruction compiled by the Plan Compiler."""
    
    def execute(self, instruction: Instruction) -> Any:
        if instruction.kind == InstructionKind.RETURN_RECORDED:
            return instruction.output_to_return
            
        raise NotImplementedError(f"Instruction {instruction.kind} is not supported in the MVP.")