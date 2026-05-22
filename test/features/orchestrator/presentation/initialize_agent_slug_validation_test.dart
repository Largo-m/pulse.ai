import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_slug_validation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

void main() {
  group('validateInitializeAgentSlug', () {
    test('returns required error when slug is empty', () {
      expect(
        validateInitializeAgentSlug(''),
        OrchestratorStrings.initializeAgentSlugRequiredError,
      );
      expect(
        validateInitializeAgentSlug('   '),
        OrchestratorStrings.initializeAgentSlugRequiredError,
      );
    });

    test('returns invalid format error for non kebab-case slug', () {
      expect(
        validateInitializeAgentSlug('Bad_Slug'),
        OrchestratorStrings.initializeAgentSlugInvalidFormatError,
      );
    });

    test('returns null for valid kebab-case slug', () {
      expect(validateInitializeAgentSlug('cursor-workflow-agents'), isNull);
    });
  });

  group('canSubmitInitializeAgentForm', () {
    const InitializeAgentBranchesState loadedBranchState =
        InitializeAgentBranchesState(
          status: BranchLoadStatus.loaded,
          branches: <String>['main'],
          selectedBranch: 'main',
        );

    test('returns false when slug is empty even if branches are ready', () {
      expect(
        canSubmitInitializeAgentForm(branchState: loadedBranchState, slug: ''),
        isFalse,
      );
    });

    test('returns true when slug and branches are valid', () {
      expect(
        canSubmitInitializeAgentForm(
          branchState: loadedBranchState,
          slug: 'my-workflow',
        ),
        isTrue,
      );
    });
  });
}
