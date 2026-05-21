import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/app/di/orchestrator_composition.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_prd_stepper_params.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_connection_banner.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_section.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_stream_panel.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart';
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

  void _ensureCubitBundle() {
    if (_cubitBundle != null) {
      return;
    }

    final OrchestratorComposition composition = context
        .read<OrchestratorComposition>();
    final PrdWorkspaceCubitBundle bundle = composition
        .createPrdWorkspaceCubitBundle();

    bundle.workflowCubit.bindWorkflow(
      workflow: widget.workflow,
      repoPath: widget.repoPath,
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
    _cubitBundle?.dispose();
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

    return MultiBlocProvider(
      providers: <BlocProvider<dynamic>>[
        BlocProvider<PrdWorkflowCubit>.value(value: bundle.workflowCubit),
        BlocProvider<PrdReviewCubit>.value(value: bundle.reviewCubit),
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
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final bool useTwoColumns =
                    constraints.maxWidth >= PulseDimensions.twoColumnBreakpoint;

                const Widget streamPanel = PrdWorkflowStreamPanel();
                const Widget reviewSection = PrdReviewSection();

                if (!useTwoColumns) {
                  return SingleChildScrollView(
                    padding: PulseInsets.pageScroll,
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(
                          maxWidth: PulseDimensions.maxContentWidth,
                        ),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            SizedBox(
                              height:
                                  PulseDimensions.workflowStreamPanelMinHeight,
                              child: streamPanel,
                            ),
                            SizedBox(height: PulseDimensions.sectionGapLg),
                            SizedBox(
                              height: PulseDimensions.prdReviewEditorMinHeight,
                              child: reviewSection,
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                }

                return Padding(
                  padding: PulseInsets.pageScroll,
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(
                        maxWidth: PulseDimensions.maxContentWidth,
                      ),
                      child: const Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Expanded(child: streamPanel),
                          SizedBox(width: PulseDimensions.sectionGapLg),
                          Expanded(flex: 2, child: reviewSection),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
