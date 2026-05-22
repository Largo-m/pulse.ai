import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdWorkflowRestoreFailurePanel extends StatelessWidget {
  const PrdWorkflowRestoreFailurePanel({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Semantics(
      container: true,
      label: OrchestratorStrings.prdWorkflowSessionRestoreFailedSemantics,
      child: DecoratedBox(
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Icon(
                    Icons.history_toggle_off_outlined,
                    size: PulseDimensions.workflowInfoBannerIconSize,
                    color: PulseColors.secondary,
                  ),
                  const SizedBox(width: PulseDimensions.sectionGapSm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          OrchestratorStrings
                              .prdWorkflowSessionRestoreFailedTitle,
                          style: textTheme.titleSmall?.copyWith(
                            color: PulseColors.onSurface,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                        Text(
                          message,
                          style: textTheme.bodyMedium?.copyWith(
                            color: PulseColors.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: PulseDimensions.sectionGapMd),
              Align(
                alignment: Alignment.centerRight,
                child: Semantics(
                  button: true,
                  label: OrchestratorStrings
                      .prdWorkflowSessionRestoreRetrySemantics,
                  child: FilledButton(
                    onPressed: () {
                      unawaited(
                        context.read<PrdWorkflowCubit>().retrySessionRestore(),
                      );
                    },
                    style: PulseButtonStyles.filledPrimary(
                      context,
                      uppercaseLabel: false,
                    ),
                    child: const Text(
                      OrchestratorStrings.prdWorkflowSessionRestoreRetryButton,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
