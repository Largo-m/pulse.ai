import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/import_project_source_card_ui_model.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/pulse_typography.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
import 'package:pulse_ai/shared/ui/mouse_hover_builder.dart';

final class ImportProjectSourceCard extends StatelessWidget {
  const ImportProjectSourceCard({super.key, required this.model});

  final ImportProjectSourceCardUiModel model;

  @override
  Widget build(BuildContext context) {
    final ImportProjectSourceCardUiModel m = model;
    final TextTheme tt = Theme.of(context).textTheme;
    return MouseHoverBuilder(
      builder: (BuildContext context, bool isHovered) {
        final Color borderColor = isHovered
            ? m.accentColor
            : PulseColors.outlineVariant;
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
                left: 0,
                top: 0,
                bottom: 0,
                child: AnimatedOpacity(
                  duration: const Duration(
                    milliseconds: PulseDimensions.borderTransitionMs,
                  ),
                  opacity: isHovered ? 1 : 0,
                  child: Container(
                    width: PulseDimensions.importSourceAccentBarWidth,
                    color: m.accentColor,
                  ),
                ),
              ),
              Padding(
                padding: PulseInsets.ctaCard,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          width: PulseDimensions.importSourceCardIconBoxSize,
                          height: PulseDimensions.importSourceCardIconBoxSize,
                          decoration: BoxDecoration(
                            color: PulseColors.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(
                              PulseRadii.importSourceIconBox,
                            ),
                          ),
                          alignment: Alignment.center,
                          child: Icon(
                            m.icon,
                            size: PulseDimensions.importSourceCardIconGlyphSize,
                            color: m.iconColor,
                          ),
                        ),
                        DecoratedBox(
                          decoration: BoxDecoration(
                            color: PulseColors.surfaceContainerHigh,
                            borderRadius: BorderRadius.circular(
                              PulseRadii.importSourceBadge,
                            ),
                            border: Border.all(
                              color: PulseColors.outlineVariant,
                            ),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal:
                                  PulseDimensions.importBadgeHorizontalPadding,
                              vertical:
                                  PulseDimensions.importBadgeVerticalPadding,
                            ),
                            child: Text(
                              m.badgeLabel.toUpperCase(),
                              style: tt.labelMedium?.copyWith(
                                color: PulseColors.outline,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(
                      height: PulseDimensions.importSourceCardHeaderGap,
                    ),
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
                        height: 1.38,
                      ),
                    ),
                    const SizedBox(
                      height: PulseDimensions.importSourceCardHeaderGap,
                    ),
                    ...m.features.map(
                      (String feature) => Padding(
                        padding: const EdgeInsets.only(
                          bottom: PulseDimensions.importFeatureListGap,
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.check_circle,
                              size: PulseDimensions.importFeatureIconSize,
                              color: PulseColors.outline,
                            ),
                            const SizedBox(
                              width: PulseDimensions.importFeatureRowGap,
                            ),
                            Text(
                              feature,
                              style: tt.labelMedium?.copyWith(
                                color: PulseColors.outline,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(
                      height: PulseDimensions.importSourceCardHeaderGap,
                    ),
                    _SourceCardButton(
                      label: m.buttonLabel,
                      trailingIcon: m.buttonTrailingIcon,
                      accentColor: m.accentColor,
                      onAccentColor: m.accentColor == PulseColors.primary
                          ? PulseColors.onPrimary
                          : PulseColors.onSecondary,
                      onPressed: m.onPressed,
                      isCardHovered: isHovered,
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

final class _SourceCardButton extends StatelessWidget {
  const _SourceCardButton({
    required this.label,
    required this.trailingIcon,
    required this.accentColor,
    required this.onAccentColor,
    required this.onPressed,
    required this.isCardHovered,
  });

  final String label;
  final IconData trailingIcon;
  final Color accentColor;
  final Color onAccentColor;
  final VoidCallback onPressed;
  final bool isCardHovered;

  @override
  Widget build(BuildContext context) {
    final Color foreground = isCardHovered
        ? onAccentColor
        : PulseColors.onSurface;
    final Color background = isCardHovered ? accentColor : Colors.transparent;
    final Color borderColor = isCardHovered
        ? accentColor
        : PulseColors.outlineVariant;
    return OutlinedButton(
      onPressed: onPressed,
      style: PulseButtonStyles.outlinedAction(
        foregroundColor: foreground,
        backgroundColor: background,
        borderColor: borderColor,
        textStyle: context.pulseCtaButtonLabel(),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label),
          const SizedBox(width: PulseDimensions.importSourceButtonGap),
          Icon(trailingIcon, size: PulseDimensions.importSourceButtonIconSize),
        ],
      ),
    );
  }
}
