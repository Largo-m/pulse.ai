import 'package:pulse_ai/features/orchestrator/domain/validators/workflow_slug_validator.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_rules.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

const WorkflowSlugValidator _slugValidator = WorkflowSlugValidator();

String? validateInitializeAgentSlug(String slug) {
  final String trimmed = slug.trim();
  if (trimmed.isEmpty) {
    return OrchestratorStrings.initializeAgentSlugRequiredError;
  }

  return _slugValidator
      .validate(trimmed)
      .fold(
        (_) => OrchestratorStrings.initializeAgentSlugInvalidFormatError,
        (_) => null,
      );
}

bool canSubmitInitializeAgentForm({
  required InitializeAgentBranchesState branchState,
  required String slug,
}) {
  return validateInitializeAgentSlug(slug) == null &&
      canSubmitInitializeAgent(branchState);
}
