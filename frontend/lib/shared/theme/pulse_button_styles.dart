import 'package:flutter/material.dart';

import 'pulse_typography.dart';
import 'tokens/pulse_colors.dart';
import 'tokens/pulse_insets.dart';
import 'tokens/pulse_radii.dart';

abstract final class PulseButtonStyles {
  static RoundedRectangleBorder get _actionButtonShape =>
      RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
      );

  static ButtonStyle filledPrimary(
    BuildContext context, {
    bool uppercaseLabel = false,
  }) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    return FilledButton.styleFrom(
      backgroundColor: PulseColors.primary,
      foregroundColor: PulseColors.onPrimary,
      padding: PulseInsets.filledActionButton,
      shape: _actionButtonShape,
      textStyle: uppercaseLabel
          ? context.pulseCtaButtonLabel()
          : textTheme.labelLarge,
    );
  }

  static ButtonStyle filledTertiary(
    BuildContext context, {
    bool uppercaseLabel = true,
  }) {
    return FilledButton.styleFrom(
      backgroundColor: PulseColors.tertiaryContainer,
      foregroundColor: PulseColors.onTertiaryContainer,
      padding: PulseInsets.filledActionButton,
      shape: _actionButtonShape,
      textStyle: uppercaseLabel ? context.pulseCtaButtonLabel() : null,
    );
  }

  static ButtonStyle outlinedAction({
    required Color foregroundColor,
    required Color backgroundColor,
    required Color borderColor,
    required TextStyle textStyle,
  }) {
    return OutlinedButton.styleFrom(
      foregroundColor: foregroundColor,
      backgroundColor: backgroundColor,
      side: BorderSide(color: borderColor),
      padding: PulseInsets.filledActionButton,
      shape: _actionButtonShape,
      textStyle: textStyle,
    );
  }
}
