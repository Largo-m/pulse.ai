import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class PrdReviewRepoContextHeader extends StatelessWidget {
  const PrdReviewRepoContextHeader({super.key, this.repoPath, this.branchName});

  final String? repoPath;
  final String? branchName;

  @override
  Widget build(BuildContext context) {
    if (repoPath == null && branchName == null) {
      return const SizedBox.shrink();
    }

    final TextTheme textTheme = Theme.of(context).textTheme;

    return Padding(
      padding: PulseInsets.prdReviewContextHeader,
      child: Wrap(
        spacing: PulseDimensions.sectionGapLg,
        runSpacing: PulseDimensions.sectionGapSm,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: <Widget>[
          if (repoPath != null)
            Semantics(
              readOnly: true,
              label: OrchestratorStrings.prdReviewRepoContextSemantics,
              child: _ContextChip(
                icon: Icons.folder_outlined,
                label: OrchestratorStrings.prdReviewRepoContextLabel,
                value: repoPath!,
                textTheme: textTheme,
              ),
            ),
          if (branchName != null)
            Semantics(
              readOnly: true,
              label: OrchestratorStrings.prdReviewBranchContextSemantics,
              child: _ContextChip(
                icon: Icons.call_split_outlined,
                label: OrchestratorStrings.prdReviewBranchContextLabel,
                value: branchName!,
                textTheme: textTheme,
              ),
            ),
        ],
      ),
    );
  }
}

final class _ContextChip extends StatelessWidget {
  const _ContextChip({
    required this.icon,
    required this.label,
    required this.value,
    required this.textTheme,
  });

  final IconData icon;
  final String label;
  final String value;
  final TextTheme textTheme;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(
          icon,
          size: PulseDimensions.prdReviewContextHeaderIconSize,
          color: PulseColors.outline,
        ),
        const SizedBox(width: PulseDimensions.sectionGapSm),
        Text(
          '$label: ',
          style: textTheme.labelSmall?.copyWith(color: PulseColors.outline),
        ),
        Text(
          value,
          style: textTheme.labelSmall?.copyWith(color: PulseColors.onSurface),
        ),
      ],
    );
  }
}
