import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
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
              final int progressPercent = workflowProgressPercent(
                phaseStatus: state.phaseStatus,
                streamLineCount: state.streamLines.length,
              );

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
                      if (state.requiresUserAction) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        const PrdWorkflowUserActionHighlight(),
                      ],
                      if (state.failureMessageKey != null) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        _FailureBanner(messageKey: state.failureMessageKey!),
                      ],
                      const SizedBox(height: PulseDimensions.sectionGapMd),
                      SizedBox(
                        height: PulseDimensions.workflowTerminalMinHeight,
                        child: WorkflowTerminalLog(lines: state.streamLines),
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
