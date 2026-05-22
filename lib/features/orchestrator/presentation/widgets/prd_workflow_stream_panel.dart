import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_session_view_mode.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_workflow_session_presentation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_workflow_start_policy.dart';
import 'package:pulse_ai/features/orchestrator/presentation/utils/workflow_progress_calculator.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_user_action_highlight.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_progress_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_section_header.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_terminal_log.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdWorkflowStreamPanel extends StatelessWidget {
  const PrdWorkflowStreamPanel({super.key, required this.workflowDirective});

  final String? workflowDirective;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: OrchestratorStrings.prdWorkflowStreamPanelSemantics,
      child: BlocBuilder<CursorConnectionCubit, CursorConnectionState>(
        builder: (BuildContext context, CursorConnectionState connectionState) {
          return BlocBuilder<PrdWorkflowCubit, PrdWorkflowState>(
            builder: (BuildContext context, PrdWorkflowState state) {
              final List<PrdStreamLineUiModel> terminalLines =
                  PrdWorkflowSessionPresentation.terminalLinesFor(state);
              final String terminalEmptyMessage =
                  PrdWorkflowSessionPresentation.terminalEmptyMessageFor(state);
              final int progressPercent = workflowProgressPercent(
                phaseStatus: state.phaseStatus,
                streamLineCount: terminalLines.length,
              );
              final bool showInProgressAffordance =
                  state.sessionViewMode == PrdSessionViewMode.inProgressOnly;

              return DecoratedBox(
                decoration: BoxDecoration(
                  color: PulseColors.surfaceContainer,
                  borderRadius: BorderRadius.circular(
                    PulseRadii.workflowStreamPanel,
                  ),
                  border: Border.all(
                    color: PulseColors.outlineVariant,
                    width: PulseDimensions.workflowStreamPanelBorderWidth,
                  ),
                ),
                child: Padding(
                  padding: PulseInsets.workflowStreamPanel,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      WorkflowSectionHeader(
                        icon: Icons.terminal,
                        title: OrchestratorStrings
                            .prdWorkflowSystemProcessingTitle,
                        trailing: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: <Widget>[
                            Text(
                              workflowProgressLabel(progressPercent),
                              style:
                                  (Theme.of(context).textTheme.labelMedium ??
                                          const TextStyle())
                                      .copyWith(
                                        color: PulseColors.primary,
                                        fontWeight: FontWeight.w600,
                                      ),
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapSm,
                            ),
                            WorkflowProgressBar(percent: progressPercent),
                          ],
                        ),
                      ),
                      if (showsPrdWorkflowStartButton(
                        state.phaseStatus,
                      )) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                        Align(
                          alignment: Alignment.centerRight,
                          child: Semantics(
                            button: true,
                            enabled: canInvokePrdWorkflowStart(
                              connectionStatus: connectionState.status,
                              isStarting: state.isStarting,
                              directive: workflowDirective,
                            ),
                            label: prdWorkflowStartButtonSemantics(
                              state.phaseStatus,
                            ),
                            child: FilledButton.icon(
                              onPressed:
                                  canInvokePrdWorkflowStart(
                                    connectionStatus: connectionState.status,
                                    isStarting: state.isStarting,
                                    directive: workflowDirective,
                                  )
                                  ? () {
                                      final String? directive =
                                          workflowDirective?.trim();
                                      if (directive == null ||
                                          directive.isEmpty) {
                                        return;
                                      }
                                      unawaited(
                                        context
                                            .read<PrdWorkflowCubit>()
                                            .startRun(directive: directive),
                                      );
                                    }
                                  : null,
                              style: PulseButtonStyles.filledPrimary(
                                context,
                                uppercaseLabel: true,
                              ),
                              icon: state.isStarting
                                  ? const SizedBox(
                                      width:
                                          PulseDimensions.sidebarTreeIconSize,
                                      height:
                                          PulseDimensions.sidebarTreeIconSize,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: PulseColors.onPrimary,
                                      ),
                                    )
                                  : const Icon(Icons.play_arrow_rounded),
                              label: Text(
                                prdWorkflowStartButtonLabel(
                                  state.phaseStatus,
                                ).toUpperCase(),
                              ),
                            ),
                          ),
                        ),
                      ],
                      if (state.canCancel) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                        Align(
                          alignment: Alignment.centerRight,
                          child: Semantics(
                            button: true,
                            label:
                                OrchestratorStrings.prdWorkflowCancelSemantics,
                            child: TextButton(
                              onPressed: state.isCancelling
                                  ? null
                                  : () {
                                      unawaited(
                                        context
                                            .read<PrdWorkflowCubit>()
                                            .cancelActiveRun(),
                                      );
                                    },
                              child: const Text(
                                OrchestratorStrings.prdWorkflowCancelButton,
                              ),
                            ),
                          ),
                        ),
                      ],
                      if (showInProgressAffordance) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        const _InProgressOnlyAffordance(),
                      ],
                      if (state.requiresUserAction) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        const PrdWorkflowUserActionHighlight(),
                      ],
                      if (PrdWorkflowSessionPresentation.showsRunFailureBanner(
                        state,
                      )) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        _FailureBanner(messageKey: state.failureMessageKey!),
                      ],
                      const SizedBox(height: PulseDimensions.sectionGapMd),
                      SizedBox(
                        height: PulseDimensions.workflowTerminalMinHeight,
                        child: WorkflowTerminalLog(
                          lines: terminalLines,
                          emptyMessage: terminalEmptyMessage,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

final class _InProgressOnlyAffordance extends StatelessWidget {
  const _InProgressOnlyAffordance();

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Semantics(
      container: true,
      label: OrchestratorStrings.prdWorkflowSessionInProgressSemantics,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: PulseColors.tertiaryContainer.withValues(
            alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
          ),
          borderRadius: BorderRadius.circular(PulseRadii.workflowInfoBanner),
          border: Border.all(
            color: PulseColors.tertiary.withValues(
              alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
            ),
          ),
        ),
        child: Padding(
          padding: PulseInsets.workflowStreamPanel,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const SizedBox(
                width: PulseDimensions.sidebarTreeIconSize,
                height: PulseDimensions.sidebarTreeIconSize,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: PulseColors.tertiary,
                ),
              ),
              const SizedBox(width: PulseDimensions.sectionGapSm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      OrchestratorStrings.prdWorkflowSessionInProgressTitle,
                      style: textTheme.titleSmall?.copyWith(
                        color: PulseColors.onSurface,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: PulseDimensions.sectionGapSm),
                    Text(
                      OrchestratorStrings.prdWorkflowSessionInProgressBody,
                      style: textTheme.bodyMedium?.copyWith(
                        color: PulseColors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

final class _FailureBanner extends StatelessWidget {
  const _FailureBanner({required this.messageKey});

  final String messageKey;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: PulseColors.surfaceContainerHigh.withValues(
          alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
        ),
        borderRadius: BorderRadius.circular(PulseRadii.workflowInfoBanner),
        border: Border.all(
          color: PulseColors.secondary.withValues(
            alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
          ),
        ),
      ),
      child: Padding(
        padding: PulseInsets.workflowStreamPanel,
        child: Text(
          messageKey,
          style: textTheme.bodyMedium?.copyWith(color: PulseColors.secondary),
        ),
      ),
    );
  }
}
