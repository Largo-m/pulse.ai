import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowUserPromptBubble extends StatelessWidget {
  const WorkflowUserPromptBubble({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Align(
      alignment: Alignment.centerRight,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth:
              MediaQuery.sizeOf(context).width *
              PulseDimensions.workflowUserBubbleMaxWidthFactor,
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: PulseColors.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(PulseRadii.workflowUserBubble),
            border: Border.all(color: PulseColors.outlineVariant),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: PulseDimensions.sectionGapMd,
              vertical: PulseDimensions.sectionGapMd,
            ),
            child: Text(
              message,
              style: textTheme.bodyMedium?.copyWith(
                color: PulseColors.onSurface,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
