import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowSectionHeader extends StatelessWidget {
  const WorkflowSectionHeader({
    super.key,
    required this.icon,
    required this.title,
    this.trailing,
  });

  final IconData icon;
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        DecoratedBox(
          decoration: BoxDecoration(
            color: PulseColors.primaryContainer.withValues(
              alpha: PulseDimensions.workflowSectionIconBackgroundAlpha,
            ),
            borderRadius: BorderRadius.circular(PulseRadii.workflowSectionIcon),
          ),
          child: SizedBox(
            width: PulseDimensions.workflowSectionIconBoxSize,
            height: PulseDimensions.workflowSectionIconBoxSize,
            child: Icon(
              icon,
              size: PulseDimensions.workflowSectionIconGlyphSize,
              color: PulseColors.primary,
            ),
          ),
        ),
        const SizedBox(width: PulseDimensions.sectionGapMd),
        Expanded(
          child: Text(
            title,
            style: (textTheme.labelMedium ?? const TextStyle()).copyWith(
              color: PulseColors.onSurface,
              fontWeight: FontWeight.w700,
              letterSpacing: PulseDimensions.workflowSectionTitleLetterSpacing,
            ),
          ),
        ),
        ?trailing,
      ],
    );
  }
}
