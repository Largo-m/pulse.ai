import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowProgressBar extends StatelessWidget {
  const WorkflowProgressBar({super.key, required this.percent});

  final int percent;

  @override
  Widget build(BuildContext context) {
    final double clamped = (percent.clamp(0, 100)) / 100;

    return SizedBox(
      width: PulseDimensions.workflowProgressBarWidth,
      height: PulseDimensions.workflowProgressBarHeight,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(PulseRadii.workflowProgressBar),
        child: ColoredBox(
          color: PulseColors.outlineVariant,
          child: Align(
            alignment: Alignment.centerLeft,
            widthFactor: clamped,
            child: const ColoredBox(color: PulseColors.primary),
          ),
        ),
      ),
    );
  }
}
