import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowTechspecInitBody extends StatelessWidget {
  const WorkflowTechspecInitBody({super.key, required this.onInitialize});

  final VoidCallback onInitialize;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Center(
      child: SingleChildScrollView(
        padding: PulseInsets.pageScroll,
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: PulseDimensions.workflowTechspecContentMaxWidth,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Text(
                OrchestratorStrings.workflowTechspecEmptyTitle,
                style: textTheme.displaySmall?.copyWith(
                  color: PulseColors.onSurface,
                  fontWeight: FontWeight.w700,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: PulseDimensions.sectionGapSm),
              Text(
                OrchestratorStrings.workflowTechspecEmptySubtitle,
                style: textTheme.bodyLarge?.copyWith(
                  color: PulseColors.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: PulseDimensions.sectionGapLg),
              Semantics(
                button: true,
                label: OrchestratorStrings.workflowTechspecInitializeSemantics,
                child: FilledButton.icon(
                  onPressed: onInitialize,
                  style: PulseButtonStyles.filledPrimary(context).copyWith(
                    padding: const WidgetStatePropertyAll<EdgeInsets>(
                      EdgeInsets.symmetric(
                        horizontal: PulseDimensions
                            .workflowInitializeButtonHorizontalPadding,
                        vertical: PulseDimensions
                            .workflowInitializeButtonVerticalPadding,
                      ),
                    ),
                    shape: const WidgetStatePropertyAll<OutlinedBorder>(
                      RoundedRectangleBorder(
                        borderRadius: BorderRadius.all(
                          Radius.circular(PulseRadii.workflowPillButton),
                        ),
                      ),
                    ),
                    elevation: const WidgetStatePropertyAll<double>(0),
                    shadowColor: WidgetStatePropertyAll<Color>(
                      PulseColors.primary.withValues(
                        alpha: PulseDimensions.workflowPrimaryButtonShadowAlpha,
                      ),
                    ),
                  ),
                  icon: const Icon(
                    Icons.auto_awesome,
                    size: PulseDimensions.chromeIconSize,
                  ),
                  label: const Text(
                    OrchestratorStrings.workflowTechspecInitializeButton,
                  ),
                ),
              ),
              const SizedBox(height: PulseDimensions.sectionGapXl),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: PulseColors.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(
                    PulseRadii.workflowInfoBanner,
                  ),
                  border: Border.all(
                    color: PulseColors.outlineVariant.withValues(
                      alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
                    ),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: PulseDimensions.sectionGapMd,
                    vertical: PulseDimensions.sectionGapSm,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const Icon(
                        Icons.info_outline,
                        size: PulseDimensions.workflowInfoBannerIconSize,
                        color: PulseColors.tertiary,
                      ),
                      const SizedBox(width: PulseDimensions.sectionGapSm),
                      Flexible(
                        child: Text(
                          OrchestratorStrings.workflowTechspecPrdCompleteBanner,
                          style: textTheme.labelMedium?.copyWith(
                            color: PulseColors.onSurfaceVariant,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
