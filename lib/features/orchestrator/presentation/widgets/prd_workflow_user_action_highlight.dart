import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdWorkflowUserActionHighlight extends StatelessWidget {
  const PrdWorkflowUserActionHighlight({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
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
            const Icon(
              Icons.touch_app_outlined,
              size: PulseDimensions.workflowStreamUserActionIconSize,
              color: PulseColors.tertiary,
            ),
            const SizedBox(width: PulseDimensions.sectionGapSm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    OrchestratorStrings.prdWorkflowUserActionRequiredTitle,
                    style: textTheme.titleSmall?.copyWith(
                      color: PulseColors.onSurface,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: PulseDimensions.sectionGapSm),
                  Text(
                    OrchestratorStrings.prdWorkflowUserActionRequiredBody,
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
    );
  }
}
