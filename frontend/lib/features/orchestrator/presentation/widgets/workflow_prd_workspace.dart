import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/app/di/orchestrator_composition.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_prd_stepper_params.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_workflow_session_presentation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_connection_banner.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_adr_list_section.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_conversation_list_section.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_new_run_overlay_banner.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_section.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_restore_failure_panel.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_stream_panel.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_user_prompt_bubble.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class WorkflowPrdWorkspace extends StatefulWidget {
  const WorkflowPrdWorkspace({
    super.key,
    required this.workflow,
    required this.repoPath,
    this.onOpenCursorSettings,
  });

  final WorkflowEntity workflow;
  final String repoPath;
  final VoidCallback? onOpenCursorSettings;

  @override
  State<WorkflowPrdWorkspace> createState() => _WorkflowPrdWorkspaceState();
}

final class _WorkflowPrdWorkspaceState extends State<WorkflowPrdWorkspace> {
  PrdWorkspaceCubitBundle? _cubitBundle;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _ensureCubitBundle();
  }

  @override
  void didUpdateWidget(WorkflowPrdWorkspace oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.workflow.workflowKey == widget.workflow.workflowKey) {
      return;
    }
    _disposeCubitBundle();
    _ensureCubitBundle();
  }

  void _disposeCubitBundle() {
    _cubitBundle?.dispose();
    _cubitBundle = null;
  }

  void _ensureCubitBundle() {
    if (_cubitBundle != null) {
      return;
    }

    final OrchestratorComposition composition = context
        .read<OrchestratorComposition>();
    final PrdWorkspaceCubitBundle bundle = composition
        .createPrdWorkspaceCubitBundle();

    unawaited(
      bundle.workflowCubit.bindWorkflow(
        workflow: widget.workflow,
        repoPath: widget.repoPath,
      ),
    );
    bundle.reviewCubit.bindReviewContext(
      projectId: widget.workflow.projectId,
      slug: widget.workflow.slug,
      repoPath: widget.repoPath,
      branchName: widget.workflow.branchName,
    );

    final CursorConnectionCubit connectionCubit = context
        .read<CursorConnectionCubit>();
    bundle.reviewCubit.syncConnectionGate(connectionCubit.state);

    bundle.adrListCubit.bindContext(
      projectId: widget.workflow.projectId,
      slug: widget.workflow.slug,
    );
    unawaited(bundle.adrListCubit.loadAdrs());

    if (connectionCubit.state.status == CursorConnectionStatus.initial) {
      unawaited(connectionCubit.runPreflight());
    }

    if (widget.workflow.prdPhaseStatus == PrdPhaseStatus.pendingApproval ||
        widget.workflow.prdPhaseStatus == PrdPhaseStatus.draft) {
      unawaited(bundle.reviewCubit.loadDraft());
    }

    _cubitBundle = bundle;
  }

  @override
  void dispose() {
    _disposeCubitBundle();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final PrdWorkspaceCubitBundle? bundle = _cubitBundle;
    if (bundle == null) {
      return const SizedBox.shrink();
    }

    final WorkflowPrdStepperParams stepperParams =
        workflowPrdStepperParamsForPhase(
          prdPhaseStatus: widget.workflow.prdPhaseStatus,
        );
    final String? directive = widget.workflow.directive?.trim();
    final bool hasDirective = directive != null && directive.isNotEmpty;

    return MultiBlocProvider(
      providers: <BlocProvider<dynamic>>[
        BlocProvider<PrdWorkflowCubit>.value(value: bundle.workflowCubit),
        BlocProvider<PrdReviewCubit>.value(value: bundle.reviewCubit),
        BlocProvider<PrdAdrListCubit>.value(value: bundle.adrListCubit),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          WorkflowPhaseStepper(
            currentPhase: stepperParams.currentPhase,
            completedPhases: stepperParams.completedPhases,
          ),
          CursorConnectionBanner(onOpenSettings: widget.onOpenCursorSettings),
          Expanded(
            child: SingleChildScrollView(
              padding: PulseInsets.pageScroll,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: PulseDimensions.workflowFeedMaxWidth,
                  ),
                  child: BlocBuilder<PrdWorkflowCubit, PrdWorkflowState>(
                    builder: (BuildContext context, PrdWorkflowState workflowState) {
                      final bool showUserBubble =
                          PrdWorkflowSessionPresentation.showsDirectiveBubble(
                            hasDirective: hasDirective,
                            state: workflowState,
                          );
                      final String? restoreFailureMessage =
                          PrdWorkflowSessionPresentation.restoreFailureDisplayMessage(
                            workflowState,
                          );

                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          if (PrdWorkflowSessionPresentation.showsNewRunOverlayBanner(
                            workflowState,
                          )) ...<Widget>[
                            const PrdNewRunOverlayBanner(),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                          ],
                          if (restoreFailureMessage != null) ...<Widget>[
                            PrdWorkflowRestoreFailurePanel(
                              message: restoreFailureMessage,
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                          ],
                          if (PrdWorkflowSessionPresentation.showsConversationSection(
                            workflowState,
                          )) ...<Widget>[
                            PrdConversationListSection(
                              messages:
                                  PrdWorkflowSessionPresentation.conversationMessagesFor(
                                    workflowState,
                                  ),
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                          ],
                          if (showUserBubble) ...<Widget>[
                            WorkflowUserPromptBubble(message: directive!),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                          ],
                          PrdWorkflowStreamPanel(
                            workflowDirective: widget.workflow.directive,
                          ),
                          const SizedBox(height: PulseDimensions.sectionGapLg),
                          PrdReviewSection(workflowSlug: widget.workflow.slug),
                          const SizedBox(height: PulseDimensions.sectionGapLg),
                          const PrdAdrListSection(),
                        ],
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
