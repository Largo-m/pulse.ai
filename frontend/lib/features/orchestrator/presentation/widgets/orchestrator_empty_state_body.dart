import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
import 'orchestrator_cta_card.dart';

final class OrchestratorEmptyStateBody extends StatelessWidget {
  const OrchestratorEmptyStateBody({
    super.key,
    required this.onSelectLocal,
    required this.onPlaceholder,
  });

  final VoidCallback onSelectLocal;
  final VoidCallback onPlaceholder;

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    final OrchestratorCtaCardUiModel localModel = OrchestratorCtaCardUiModel(
      title: OrchestratorStrings.localProjectTitle,
      body: OrchestratorStrings.localProjectBody,
      icon: Icons.folder_open,
      accentBorderHover: PulseColors.primary,
      iconColor: PulseColors.primary,
      buttonLabel: OrchestratorStrings.localProjectButton,
      usesPrimaryButtonStyle: true,
      onPressed: onSelectLocal,
    );
    final OrchestratorCtaCardUiModel remoteModel = OrchestratorCtaCardUiModel(
      title: OrchestratorStrings.remoteProjectTitle,
      body: OrchestratorStrings.remoteProjectBody,
      icon: Icons.cloud_download_outlined,
      accentBorderHover: PulseColors.tertiary,
      iconColor: PulseColors.tertiary,
      buttonLabel: OrchestratorStrings.remoteProjectButton,
      usesPrimaryButtonStyle: false,
      onPressed: onPlaceholder,
    );
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints c) {
        final bool isWide = c.maxWidth >= PulseDimensions.twoColumnBreakpoint;
        return SingleChildScrollView(
          padding: PulseInsets.pageScroll,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: PulseDimensions.maxContentWidth,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: PulseDimensions.bodyTopSpacer),
                  SizedBox(
                    width: PulseDimensions.heroIconContainerSize,
                    height: PulseDimensions.heroIconContainerSize,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: PulseColors.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(
                          PulseRadii.heroIconContainer,
                        ),
                        border: Border.all(color: PulseColors.outlineVariant),
                      ),
                      child: const Icon(
                        Icons.memory,
                        size: PulseDimensions.heroIconGlyphSize,
                        color: PulseColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(height: PulseDimensions.sectionGapMd),
                  Text(
                    OrchestratorStrings.emptyStateTitle,
                    style: tt.displaySmall?.copyWith(
                      color: PulseColors.onSurface,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: PulseDimensions.sectionGapSm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: PulseDimensions.maxIntroTextWidth,
                    ),
                    child: Text(
                      OrchestratorStrings.emptyStateSubtitle,
                      style: tt.bodyLarge?.copyWith(
                        color: PulseColors.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: PulseDimensions.sectionGapXl),
                  if (isWide)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(child: OrchestratorCtaCard(model: localModel)),
                        const SizedBox(width: PulseDimensions.ctaColumnGap),
                        Expanded(
                          child: OrchestratorCtaCard(model: remoteModel),
                        ),
                      ],
                    )
                  else
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        OrchestratorCtaCard(model: localModel),
                        const SizedBox(height: PulseDimensions.ctaColumnGap),
                        OrchestratorCtaCard(model: remoteModel),
                      ],
                    ),
                  const SizedBox(height: PulseDimensions.bodyTopSpacer),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
