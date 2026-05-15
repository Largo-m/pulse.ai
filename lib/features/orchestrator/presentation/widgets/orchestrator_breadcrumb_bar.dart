import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_pulsing_dot.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_radii.dart';

final class OrchestratorBreadcrumbBar extends StatelessWidget {
  const OrchestratorBreadcrumbBar({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    return SizedBox(
      height: GovernanceDimensions.breadcrumbBarHeight,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: GovernanceColors.surfaceContainerLow,
          border: Border(
            bottom: BorderSide(color: GovernanceColors.outlineVariant),
          ),
        ),
        child: Padding(
          padding: GovernanceInsets.breadcrumbHorizontal,
          child: Row(
            children: [
              Text(
                OrchestratorStrings.breadcrumbSystem,
                style: tt.labelMedium?.copyWith(color: GovernanceColors.outline),
              ),
              const Icon(
                Icons.chevron_right,
                size: GovernanceDimensions.chevronIconSize,
                color: GovernanceColors.outline,
              ),
              Text(
                OrchestratorStrings.breadcrumbInitialization,
                style: tt.labelMedium?.copyWith(
                  color: GovernanceColors.onSurface,
                ),
              ),
              const Spacer(),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: GovernanceColors.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(
                    GovernanceRadii.standbyChip,
                  ),
                  border: Border.all(color: GovernanceColors.outlineVariant),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal:
                        GovernanceDimensions.standbyChipHorizontalPadding,
                    vertical: GovernanceDimensions.standbyChipVerticalPadding,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const OrchestratorPulsingDot(),
                      const SizedBox(
                        width: GovernanceDimensions.standbyLabelGap,
                      ),
                      Text(
                        OrchestratorStrings.statusStandby,
                        style: tt.labelMedium?.copyWith(
                          color: GovernanceColors.tertiary,
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
