import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_rules.dart';

void main() {
  group('canSubmitInitializeAgent', () {
    test('returns true when loaded with selected branch in list', () {
      const InitializeAgentBranchesState state = InitializeAgentBranchesState(
        status: BranchLoadStatus.loaded,
        branches: <String>['main', 'develop'],
        selectedBranch: 'main',
      );

      expect(canSubmitInitializeAgent(state), isTrue);
    });

    test('returns false when loaded with null selectedBranch', () {
      const InitializeAgentBranchesState state = InitializeAgentBranchesState(
        status: BranchLoadStatus.loaded,
        branches: <String>['main', 'develop'],
      );

      expect(canSubmitInitializeAgent(state), isFalse);
    });

    test('returns false when selected branch is not in branches list', () {
      const InitializeAgentBranchesState state = InitializeAgentBranchesState(
        status: BranchLoadStatus.loaded,
        branches: <String>['main'],
        selectedBranch: 'develop',
      );

      expect(canSubmitInitializeAgent(state), isFalse);
    });

    test('returns false for notGitRepository status', () {
      const InitializeAgentBranchesState state = InitializeAgentBranchesState(
        status: BranchLoadStatus.notGitRepository,
      );

      expect(canSubmitInitializeAgent(state), isFalse);
    });

    test('returns false for failure and loading statuses', () {
      expect(
        canSubmitInitializeAgent(
          const InitializeAgentBranchesState(status: BranchLoadStatus.failure),
        ),
        isFalse,
      );
      expect(
        canSubmitInitializeAgent(
          const InitializeAgentBranchesState(status: BranchLoadStatus.loading),
        ),
        isFalse,
      );
    });
  });
}
