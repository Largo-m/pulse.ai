import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';

bool canSubmitInitializeAgent(InitializeAgentBranchesState branchState) {
  final String? selectedBranch = branchState.selectedBranch;
  return branchState.status == BranchLoadStatus.loaded &&
      selectedBranch != null &&
      branchState.branches.contains(selectedBranch);
}
