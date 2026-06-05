import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';

enum PulseFilledActionButtonVariant { primary, tertiary }

final class PulseFilledActionButton extends StatelessWidget {
  const PulseFilledActionButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = PulseFilledActionButtonVariant.primary,
    this.uppercaseLabel = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final PulseFilledActionButtonVariant variant;
  final bool uppercaseLabel;

  @override
  Widget build(BuildContext context) {
    final ButtonStyle style = switch (variant) {
      PulseFilledActionButtonVariant.primary => PulseButtonStyles.filledPrimary(
        context,
        uppercaseLabel: uppercaseLabel,
      ),
      PulseFilledActionButtonVariant.tertiary =>
        PulseButtonStyles.filledTertiary(
          context,
          uppercaseLabel: uppercaseLabel,
        ),
    };
    final String displayLabel = uppercaseLabel ? label.toUpperCase() : label;

    return FilledButton(
      onPressed: onPressed,
      style: style,
      child: Text(displayLabel),
    );
  }
}
