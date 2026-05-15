import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_radii.dart';
import 'orchestrator_cta_card.dart';

final class OrchestratorEmptyStateBody extends StatelessWidget {
  const OrchestratorEmptyStateBody({super.key, required this.onPlaceholder});

  final VoidCallback onPlaceholder;

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    final OrchestratorCtaCardUiModel localModel = OrchestratorCtaCardUiModel(
      title: 'Open Local Project',
      body:
          'Mount a local directory containing your agent configuration files and task graphs.',
      icon: Icons.folder_open,
      accentBorderHover: GovernanceColors.primary,
      iconColor: GovernanceColors.primary,
      buttonLabel: 'Initialize Local',
      usesPrimaryButtonStyle: true,
      onPressed: onPlaceholder,
    );
    final OrchestratorCtaCardUiModel remoteModel = OrchestratorCtaCardUiModel(
      title: 'Clone Git Repository',
      body:
          'Synchronize an existing orchestration project from GitHub, GitLab, or a custom remote.',
      icon: Icons.cloud_download_outlined,
      accentBorderHover: GovernanceColors.tertiary,
      iconColor: GovernanceColors.tertiary,
      buttonLabel: 'Connect Remote',
      usesPrimaryButtonStyle: false,
      onPressed: onPlaceholder,
    );
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints c) {
        final bool isWide =
            c.maxWidth >= GovernanceDimensions.twoColumnBreakpoint;
        return SingleChildScrollView(
          padding: GovernanceInsets.pageScroll,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: GovernanceDimensions.maxContentWidth,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: GovernanceDimensions.bodyTopSpacer),
                  SizedBox(
                    width: GovernanceDimensions.heroIconContainerSize,
                    height: GovernanceDimensions.heroIconContainerSize,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: GovernanceColors.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(
                          GovernanceRadii.heroIconContainer,
                        ),
                        border: Border.all(
                          color: GovernanceColors.outlineVariant,
                        ),
                      ),
                      child: const Icon(
                        Icons.memory,
                        size: GovernanceDimensions.heroIconGlyphSize,
                        color: GovernanceColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(height: GovernanceDimensions.sectionGapMd),
                  Text(
                    'Welcome to Neural Shell Systems',
                    style: tt.displaySmall?.copyWith(
                      color: GovernanceColors.onSurface,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: GovernanceDimensions.sectionGapSm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: GovernanceDimensions.maxIntroTextWidth,
                    ),
                    child: Text(
                      'The agentic orchestration environment is initialized and standing by. Configure your workspace to begin managing multi-agent workflows.',
                      style: tt.bodyLarge?.copyWith(
                        color: GovernanceColors.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: GovernanceDimensions.sectionGapXl),
                  if (isWide)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(child: OrchestratorCtaCard(model: localModel)),
                        const SizedBox(width: GovernanceDimensions.ctaColumnGap),
                        Expanded(child: OrchestratorCtaCard(model: remoteModel)),
                      ],
                    )
                  else
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        OrchestratorCtaCard(model: localModel),
                        const SizedBox(height: GovernanceDimensions.ctaColumnGap),
                        OrchestratorCtaCard(model: remoteModel),
                      ],
                    ),
                  const SizedBox(height: GovernanceDimensions.bodyTopSpacer),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
