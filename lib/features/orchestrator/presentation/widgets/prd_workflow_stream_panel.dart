import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_status_chip.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_workflow_user_action_highlight.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdWorkflowStreamPanel extends StatelessWidget {
  const PrdWorkflowStreamPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: OrchestratorStrings.prdWorkflowStreamPanelSemantics,
      child: BlocBuilder<PrdWorkflowCubit, PrdWorkflowState>(
        builder: (BuildContext context, PrdWorkflowState state) {
          return DecoratedBox(
            decoration: BoxDecoration(
              color: PulseColors.surfaceContainerLowest,
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
                  Row(
                    children: <Widget>[
                      PrdWorkflowStatusChip(state: state),
                      const Spacer(),
                      if (state.canCancel)
                        Semantics(
                          button: true,
                          label: OrchestratorStrings.prdWorkflowCancelSemantics,
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
                    ],
                  ),
                  if (state.requiresUserAction) ...<Widget>[
                    const SizedBox(height: PulseDimensions.sectionGapMd),
                    const PrdWorkflowUserActionHighlight(),
                  ],
                  if (state.failureMessageKey != null) ...<Widget>[
                    const SizedBox(height: PulseDimensions.sectionGapMd),
                    _FailureBanner(messageKey: state.failureMessageKey!),
                  ],
                  const SizedBox(height: PulseDimensions.sectionGapMd),
                  Expanded(child: _StreamLinesList(lines: state.streamLines)),
                ],
              ),
            ),
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

final class _StreamLinesList extends StatelessWidget {
  const _StreamLinesList({required this.lines});

  final List<PrdStreamLineUiModel> lines;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    if (lines.isEmpty) {
      return Center(
        child: Text(
          OrchestratorStrings.prdWorkflowStreamEmpty,
          style: textTheme.bodyMedium?.copyWith(
            color: PulseColors.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      );
    }

    return ListView.separated(
      itemCount: lines.length,
      separatorBuilder: (BuildContext context, int index) {
        return const SizedBox(height: PulseDimensions.sectionGapSm);
      },
      itemBuilder: (BuildContext context, int index) {
        final PrdStreamLineUiModel line = lines[index];
        final TextStyle baseStyle =
            textTheme.bodySmall?.copyWith(color: PulseColors.onSurface) ??
            const TextStyle();

        return Semantics(
          label: line.displayText,
          child: DecoratedBox(
            decoration: line.requiresUserAction
                ? BoxDecoration(
                    color: PulseColors.tertiaryContainer.withValues(
                      alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
                    ),
                    borderRadius: BorderRadius.circular(
                      PulseRadii.workflowStreamPanel,
                    ),
                  )
                : const BoxDecoration(),
            child: Padding(
              padding: line.requiresUserAction
                  ? PulseInsets.workflowStreamChip
                  : EdgeInsets.zero,
              child: Text(line.displayText, style: baseStyle),
            ),
          ),
        );
      },
    );
  }
}
