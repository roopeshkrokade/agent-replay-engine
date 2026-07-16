from typing import Mapping, Any
from compiler import ReplayPlan
from .matcher import ExactMatcher
from .executor import InstructionExecutor
from .models import ReplayResult

class ReplayVM:
    """
    The deterministic virtual machine. 
    It maintains the execution cursor and evaluates the bytecode.
    """
    def __init__(self, plan: ReplayPlan):
        self.plan = plan
        self.cursor = 0
        self.matcher = ExactMatcher()
        self.executor = InstructionExecutor()

    def advance(self, app_input: Mapping[str, Any]) -> ReplayResult:
        """Simulates an application intercepting an SDK call and asking the engine what to do."""
        if self.cursor >= len(self.plan.instructions):
            raise RuntimeError("End of Replay Plan reached. The agent over-executed.")
        
        instruction = self.plan.instructions[self.cursor]
        
        # 1. Resolve matching strategy
        resolution = self.matcher.resolve(app_input, instruction)
        
        # If the app deviates from the plan in Cache mode, execution fails deterministically.
        if resolution.confidence < 1.0:
            return ReplayResult(success=False, output=None, resolution=resolution)
            
        # 2. Execute the action
        output = self.executor.execute(instruction)
        
        # 3. Advance the VM state
        self.cursor += 1
        
        return ReplayResult(success=True, output=output, resolution=resolution)