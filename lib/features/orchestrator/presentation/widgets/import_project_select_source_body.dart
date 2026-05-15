import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/import_project_source_card_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/import_project_atmospheric_background.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/import_project_source_card.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class ImportProjectSelectSourceBody extends StatelessWidget {
  const ImportProjectSelectSourceBody({
    super.key,
    required this.onSelectLocal,
    required this.onPlaceholder,
  });

  final VoidCallback onSelectLocal;
  final VoidCallback onPlaceholder;

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    final ImportProjectSourceCardUiModel localModel =
        ImportProjectSourceCardUiModel(
          badgeLabel: ImportProjectStrings.localBadge,
          title: ImportProjectStrings.localTitle,
          body: ImportProjectStrings.localBody,
          features: const <String>[
            ImportProjectStrings.localFeatureZeroLatency,
            ImportProjectStrings.localFeatureDirectIo,
          ],
          buttonLabel: ImportProjectStrings.selectLocal,
          icon: Icons.folder_open_outlined,
          buttonTrailingIcon: Icons.arrow_forward,
          accentColor: PulseColors.primary,
          iconColor: PulseColors.primary,
          onPressed: onSelectLocal,
        );
    final ImportProjectSourceCardUiModel remoteModel =
        ImportProjectSourceCardUiModel(
          badgeLabel: ImportProjectStrings.remoteBadge,
          title: ImportProjectStrings.remoteTitle,
          body: ImportProjectStrings.remoteBody,
          features: const <String>[
            ImportProjectStrings.remoteFeatureGitAuth,
            ImportProjectStrings.remoteFeatureBranchManagement,
          ],
          buttonLabel: ImportProjectStrings.selectRemote,
          icon: Icons.cloud_sync_outlined,
          buttonTrailingIcon: Icons.hub_outlined,
          accentColor: PulseColors.secondary,
          iconColor: PulseColors.secondary,
          onPressed: onPlaceholder,
        );
    return Stack(
      fit: StackFit.expand,
      children: [
        const ImportProjectAtmosphericBackground(),
        LayoutBuilder(
          builder: (BuildContext context, BoxConstraints constraints) {
            final bool isWide =
                constraints.maxWidth >= PulseDimensions.twoColumnBreakpoint;
            return SingleChildScrollView(
              padding: PulseInsets.pageScroll,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: PulseDimensions.importPageMaxWidth,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(height: PulseDimensions.bodyTopSpacer),
                      Text(
                        ImportProjectStrings.pageTitle,
                        style: tt.displaySmall?.copyWith(
                          color: PulseColors.onSurface,
                        ),
                      ),
                      const SizedBox(height: PulseDimensions.sectionGapSm),
                      Text(
                        ImportProjectStrings.pageSubtitle,
                        style: tt.bodyLarge?.copyWith(
                          color: PulseColors.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(
                        height: PulseDimensions.importHeaderBottomGap,
                      ),
                      if (isWide)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: ImportProjectSourceCard(model: localModel),
                            ),
                            const SizedBox(width: PulseDimensions.ctaColumnGap),
                            Expanded(
                              child: ImportProjectSourceCard(
                                model: remoteModel,
                              ),
                            ),
                          ],
                        )
                      else
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            ImportProjectSourceCard(model: localModel),
                            const SizedBox(
                              height: PulseDimensions.ctaColumnGap,
                            ),
                            ImportProjectSourceCard(model: remoteModel),
                          ],
                        ),
                      const SizedBox(height: PulseDimensions.bodyTopSpacer),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}
