import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_pulsing_dot.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class OrchestratorBreadcrumbBar extends StatelessWidget {
  const OrchestratorBreadcrumbBar({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    return SizedBox(
      height: PulseDimensions.breadcrumbBarHeight,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: PulseColors.surfaceContainerLow,
          border: Border(bottom: BorderSide(color: PulseColors.outlineVariant)),
        ),
        child: Padding(
          padding: PulseInsets.breadcrumbHorizontal,
          child: Row(
            children: [
              Text(
                OrchestratorStrings.breadcrumbSystem,
                style: tt.labelMedium?.copyWith(color: PulseColors.outline),
              ),
              const Icon(
                Icons.chevron_right,
                size: PulseDimensions.chevronIconSize,
                color: PulseColors.outline,
              ),
              Text(
                OrchestratorStrings.breadcrumbInitialization,
                style: tt.labelMedium?.copyWith(color: PulseColors.onSurface),
              ),
              const Spacer(),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: PulseColors.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                  border: Border.all(color: PulseColors.outlineVariant),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: PulseDimensions.standbyChipHorizontalPadding,
                    vertical: PulseDimensions.standbyChipVerticalPadding,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const OrchestratorPulsingDot(),
                      const SizedBox(width: PulseDimensions.standbyLabelGap),
                      Text(
                        OrchestratorStrings.statusStandby,
                        style: tt.labelMedium?.copyWith(
                          color: PulseColors.tertiary,
                        ),
                      ),
                    ],
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
