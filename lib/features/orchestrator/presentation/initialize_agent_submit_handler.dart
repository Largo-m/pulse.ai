import 'dart:async';

import 'package:flutter/material.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/create_workflow_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_workflow_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

abstract final class InitializeAgentSubmitHandler {
  static Future<void> handle({
    required BuildContext context,
    required OrchestratorMainContentCubit mainContentCubit,
    required RecentProjectsCubit recentProjectsCubit,
    required CreateWorkflowUseCase createWorkflowUseCase,
    required InitializeAgentSubmitPayload payload,
  }) async {
    final Either<Failure, WorkflowEntity> result = await createWorkflowUseCase(
      projectId: payload.projectId,
      slug: payload.slug,
      branchName: payload.branchName,
      directive: payload.coreDirective,
    );

    if (!context.mounted) {
      return;
    }

    result.fold(
      (Failure failure) {
        InitializeAgentWorkflowFeedback.showCreateWorkflowFailure(
          context,
          failure: failure,
        );
      },
      (WorkflowEntity workflow) {
        mainContentCubit.showPrdWorkflow(agent: payload, workflow: workflow);
        unawaited(recentProjectsCubit.refresh());
      },
    );
  }
}
