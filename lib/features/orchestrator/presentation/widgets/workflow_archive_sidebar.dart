import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowArchiveSidebar extends StatelessWidget {
  const WorkflowArchiveSidebar({
    super.key,
    required this.artifactFileName,
    required this.isApproved,
  });

  final String artifactFileName;
  final bool isApproved;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return SizedBox(
      width: PulseDimensions.workflowArchiveSidebarWidth,
      child: ColoredBox(
        color: PulseColors.surfaceContainerLow,
        child: DecoratedBox(
          decoration: const BoxDecoration(
            border: Border(left: BorderSide(color: PulseColors.outlineVariant)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Padding(
                padding: PulseInsets.workflowArchiveHeader,
                child: Text(
                  OrchestratorStrings.workflowArchiveTitle,
                  style: (textTheme.labelLarge ?? const TextStyle()).copyWith(
                    color: PulseColors.outline,
                    letterSpacing:
                        PulseDimensions.sidebarSectionTitleLetterSpacing,
                  ),
                ),
              ),
              Expanded(
                child: ListView(
                  padding: PulseInsets.workflowArchiveList,
                  children: <Widget>[
                    _ArchiveArtifactCard(
                      fileName: artifactFileName,
                      isApproved: isApproved,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

final class _ArchiveArtifactCard extends StatelessWidget {
  const _ArchiveArtifactCard({
    required this.fileName,
    required this.isApproved,
  });

  final String fileName;
  final bool isApproved;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: PulseColors.surfaceContainer,
        borderRadius: BorderRadius.circular(PulseRadii.workflowArchiveCard),
        border: Border.all(color: PulseColors.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(PulseDimensions.sectionGapMd),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Icon(
              Icons.description_outlined,
              size: PulseDimensions.workflowArchiveDocumentIconSize,
              color: PulseColors.tertiary,
            ),
            const SizedBox(width: PulseDimensions.sectionGapMd),
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
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (isApproved) ...<Widget>[
                    const SizedBox(height: PulseDimensions.sectionGapSm),
                    DecoratedBox(
                      decoration: BoxDecoration(
                        color: PulseColors.tertiaryContainer.withValues(
                          alpha: PulseDimensions.workflowArchiveApprovedAlpha,
                        ),
                        borderRadius: BorderRadius.circular(
                          PulseRadii.workflowArchiveStatus,
                        ),
                      ),
                      child: Padding(
                        padding: PulseInsets.workflowArchiveStatus,
                        child: Text(
                          OrchestratorStrings.workflowArchiveApprovedStatus,
                          style: textTheme.labelSmall?.copyWith(
                            color: PulseColors.tertiary,
                            fontWeight: FontWeight.w700,
                            letterSpacing: PulseDimensions
                                .workflowSectionTitleLetterSpacing,
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
