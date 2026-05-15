import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';
import 'package:pulse_ai/shared/theme/pulse_typography.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
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
            : PulseColors.outlineVariant;
        final double watermarkOpacity = isHovered
            ? PulseDimensions.watermarkOpacityHover
            : PulseDimensions.watermarkOpacityRest;
        return AnimatedContainer(
          duration: const Duration(
            milliseconds: PulseDimensions.borderTransitionMs,
          ),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            color: PulseColors.surfaceContainerLow,
            borderRadius: BorderRadius.circular(PulseRadii.ctaCard),
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
                    padding: PulseInsets.watermark,
                    child: Icon(
                      m.icon,
                      size: PulseDimensions.watermarkIconSize,
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
                    alpha: PulseDimensions.inkHoverAlpha,
                  ),
                  child: Padding(
                    padding: PulseInsets.ctaCard,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(
                            milliseconds: PulseDimensions.borderTransitionMs,
                          ),
                          width: PulseDimensions.ctaIconBoxSize,
                          height: PulseDimensions.ctaIconBoxSize,
                          decoration: BoxDecoration(
                            color: PulseColors.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(
                              PulseRadii.ctaIconBox,
                            ),
                            border: Border.all(color: borderColor),
                          ),
                          alignment: Alignment.center,
                          child: Icon(m.icon, color: m.iconColor),
                        ),
                        const SizedBox(height: PulseDimensions.sectionGapMd),
                        Text(
                          m.title,
                          style: tt.headlineSmall?.copyWith(
                            color: PulseColors.onSurface,
                          ),
                        ),
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                        Text(
                          m.body,
                          style: tt.bodyMedium?.copyWith(
                            color: PulseColors.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: PulseDimensions.sectionGapLg),
                        if (m.usesPrimaryButtonStyle)
                          FilledButton(
                            onPressed: m.onPressed,
                            style: FilledButton.styleFrom(
                              backgroundColor: PulseColors.primary,
                              foregroundColor: PulseColors.onPrimary,
                              textStyle: context.pulseCtaButtonLabel(),
                              padding: PulseInsets.ctaButton,
                            ),
                            child: Text(m.buttonLabel.toUpperCase()),
                          )
                        else
                          FilledButton(
                            onPressed: m.onPressed,
                            style: FilledButton.styleFrom(
                              backgroundColor: PulseColors.tertiaryContainer,
                              foregroundColor: PulseColors.onTertiaryContainer,
                              textStyle: context.pulseCtaButtonLabel(),
                              padding: PulseInsets.ctaButton,
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
