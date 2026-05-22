import 'package:flutter/material.dart';

import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

abstract final class InitializeAgentWorkflowFeedback {
  static String resolveFailureMessage(Failure failure) {
    if (failure is WorkflowPersistenceFailure) {
      return switch (failure.code) {
        WorkflowPersistenceFailureCode.slugCollision =>
          OrchestratorStrings.initializeAgentSlugCollisionError,
        WorkflowPersistenceFailureCode.invalidSlug =>
          OrchestratorStrings.initializeAgentSlugInvalidFormatError,
        _ => OrchestratorStrings.initializeAgentCreateWorkflowFailure,
      };
    }

    return OrchestratorStrings.initializeAgentCreateWorkflowFailure;
  }

  static void showCreateWorkflowFailure(
    BuildContext context, {
    required Failure failure,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(resolveFailureMessage(failure)),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
