import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdArtifactCard extends StatelessWidget {
  const PrdArtifactCard({
    super.key,
    required this.fileName,
    required this.child,
    required this.footer,
    this.subtitle,
  });

  final String fileName;
  final String? subtitle;
  final Widget child;
  final Widget footer;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: PulseColors.surfaceContainer,
        borderRadius: BorderRadius.circular(PulseRadii.workflowArtifactCard),
        border: Border.all(color: PulseColors.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          DecoratedBox(
            decoration: const BoxDecoration(
              color: PulseColors.surfaceContainerLow,
              border: Border(
                bottom: BorderSide(color: PulseColors.outlineVariant),
              ),
              borderRadius: BorderRadius.vertical(
                top: Radius.circular(PulseRadii.workflowArtifactCard),
              ),
            ),
            child: Padding(
              padding: PulseInsets.prdArtifactTitleBar,
              child: Row(
                children: <Widget>[
                  const Icon(
                    Icons.article_outlined,
                    size: PulseDimensions.prdArtifactTitleIconSize,
                    color: PulseColors.primary,
                  ),
                  const SizedBox(width: PulseDimensions.sectionGapSm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          fileName,
                          style: textTheme.labelMedium?.copyWith(
                            color: PulseColors.onSurface,
                            fontWeight: FontWeight.w600,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (subtitle != null) ...<Widget>[
                          const SizedBox(
                            height: PulseDimensions.sectionGapSm / 2,
                          ),
                          Text(
                            subtitle!,
                            style: textTheme.labelSmall?.copyWith(
                              color: PulseColors.onSurfaceVariant,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                  Semantics(
                    label: OrchestratorStrings.prdArtifactExpandSemantics,
                    child: const Icon(
                      Icons.open_in_full,
                      size: PulseDimensions.prdArtifactTitleIconSize,
                      color: PulseColors.outline,
                    ),
                  ),
                ],
              ),
            ),
          ),
          SizedBox(
            height: PulseDimensions.prdArtifactBodyMinHeight,
            child: child,
          ),
          DecoratedBox(
            decoration: const BoxDecoration(
              border: Border(
                top: BorderSide(color: PulseColors.outlineVariant),
              ),
            ),
            child: Padding(
              padding: PulseInsets.prdReviewActionBar,
              child: footer,
            ),
          ),
        ],
      ),
    );
  }
}
