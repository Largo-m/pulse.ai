import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';
import 'package:pulse_ai/shared/theme/governance_typography.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_radii.dart';
import 'package:pulse_ai/shared/ui/mouse_hover_builder.dart';

final class OrchestratorCtaCard extends StatelessWidget {
  const OrchestratorCtaCard({super.key, required this.model});

  final OrchestratorCtaCardUiModel model;

  @override
  Widget build(BuildContext context) {
    final OrchestratorCtaCardUiModel m = model;
    final TextTheme tt = Theme.of(context).textTheme;
    return MouseHoverBuilder(
      builder: (BuildContext context, bool isHovered) {
        final Color borderColor = isHovered
            ? m.accentBorderHover
            : GovernanceColors.outlineVariant;
        final double watermarkOpacity = isHovered
            ? GovernanceDimensions.watermarkOpacityHover
            : GovernanceDimensions.watermarkOpacityRest;
        return AnimatedContainer(
          duration: const Duration(
            milliseconds: GovernanceDimensions.borderTransitionMs,
          ),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            color: GovernanceColors.surfaceContainerLow,
            borderRadius: BorderRadius.circular(GovernanceRadii.ctaCard),
            border: Border.all(color: borderColor),
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(
            children: [
              Positioned(
                top: 0,
                right: 0,
                child: Opacity(
                  opacity: watermarkOpacity,
                  child: Padding(
                    padding: GovernanceInsets.watermark,
                    child: Icon(
                      m.icon,
                      size: GovernanceDimensions.watermarkIconSize,
                      color: m.iconColor,
                    ),
                  ),
                ),
              ),
              Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: m.onPressed,
                  hoverColor: Colors.white.withValues(
                    alpha: GovernanceDimensions.inkHoverAlpha,
                  ),
                  child: Padding(
                    padding: GovernanceInsets.ctaCard,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(
                            milliseconds:
                                GovernanceDimensions.borderTransitionMs,
                          ),
                          width: GovernanceDimensions.ctaIconBoxSize,
                          height: GovernanceDimensions.ctaIconBoxSize,
                          decoration: BoxDecoration(
                            color: GovernanceColors.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(
                              GovernanceRadii.ctaIconBox,
                            ),
                            border: Border.all(color: borderColor),
                          ),
                          alignment: Alignment.center,
                          child: Icon(m.icon, color: m.iconColor),
                        ),
                        const SizedBox(
                          height: GovernanceDimensions.sectionGapMd,
                        ),
                        Text(
                          m.title,
                          style: tt.headlineSmall?.copyWith(
                            color: GovernanceColors.onSurface,
                          ),
                        ),
                        const SizedBox(
                          height: GovernanceDimensions.sectionGapSm,
                        ),
                        Text(
                          m.body,
                          style: tt.bodyMedium?.copyWith(
                            color: GovernanceColors.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(
                          height: GovernanceDimensions.sectionGapLg,
                        ),
                        if (m.usesPrimaryButtonStyle)
                          FilledButton(
                            onPressed: m.onPressed,
                            style: FilledButton.styleFrom(
                              backgroundColor: GovernanceColors.primary,
                              foregroundColor: GovernanceColors.onPrimary,
                              textStyle: context.governanceCtaButtonLabel(),
                              padding: GovernanceInsets.ctaButton,
                            ),
                            child: Text(m.buttonLabel.toUpperCase()),
                          )
                        else
                          FilledButton(
                            onPressed: m.onPressed,
                            style: FilledButton.styleFrom(
                              backgroundColor:
                                  GovernanceColors.tertiaryContainer,
                              foregroundColor:
                                  GovernanceColors.onTertiaryContainer,
                              textStyle: context.governanceCtaButtonLabel(),
                              padding: GovernanceInsets.ctaButton,
                            ),
                            child: Text(m.buttonLabel.toUpperCase()),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
