import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
import 'package:pulse_ai/shared/ui/mouse_hover_builder.dart';

final class PulseChromeIconButton extends StatelessWidget {
  const PulseChromeIconButton({
    super.key,
    required this.icon,
    required this.onPressed,
    this.tooltip,
    this.semanticsLabel,
    this.iconSize = PulseDimensions.chromeIconSize,
    this.showBorderOnHover = false,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String? tooltip;
  final String? semanticsLabel;
  final double iconSize;
  final bool showBorderOnHover;

  @override
  Widget build(BuildContext context) {
    final Widget button = Semantics(
      button: true,
      label: semanticsLabel ?? tooltip,
      child: MouseHoverBuilder(
        builder: (BuildContext context, bool isHovered) {
          final Color borderColor = showBorderOnHover && isHovered
              ? PulseColors.outlineVariant
              : Colors.transparent;
          final Color backgroundColor = isHovered
              ? PulseColors.surfaceContainerHighest
              : Colors.transparent;
          final Color iconColor = showBorderOnHover
              ? (isHovered ? PulseColors.primary : PulseColors.outline)
              : PulseColors.onSurfaceVariant;

          return Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onPressed,
              borderRadius: BorderRadius.circular(PulseRadii.actionButton),
              child: AnimatedContainer(
                duration: const Duration(
                  milliseconds: PulseDimensions.borderTransitionMs,
                ),
                curve: Curves.easeInOut,
                decoration: BoxDecoration(
                  color: backgroundColor,
                  borderRadius: BorderRadius.circular(PulseRadii.actionButton),
                  border: Border.all(color: borderColor),
                ),
                child: Padding(
                  padding: PulseInsets.chromeIconButton,
                  child: Icon(icon, size: iconSize, color: iconColor),
                ),
              ),
            ),
          );
        },
      ),
    );

    if (tooltip == null) {
      return button;
    }

    return Tooltip(message: tooltip!, child: button);
  }
}
