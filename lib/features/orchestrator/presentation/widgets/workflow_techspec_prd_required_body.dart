import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class WorkflowTechspecPrdRequiredBody extends StatelessWidget {
  const WorkflowTechspecPrdRequiredBody({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Semantics(
      container: true,
      label: OrchestratorStrings.workflowTechspecPrdRequiredSemantics,
      child: Center(
        child: SingleChildScrollView(
          padding: PulseInsets.pageScroll,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: PulseDimensions.workflowTechspecContentMaxWidth,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                const Icon(
                  Icons.lock_outline,
                  size: PulseDimensions.workflowInfoBannerIconSize,
                  color: PulseColors.onSurfaceVariant,
                ),
                const SizedBox(height: PulseDimensions.sectionGapMd),
                Text(
                  OrchestratorStrings.workflowTechspecPrdRequiredTitle,
                  style: textTheme.displaySmall?.copyWith(
                    color: PulseColors.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: PulseDimensions.sectionGapSm),
                Text(
                  OrchestratorStrings.workflowTechspecPrdRequiredSubtitle,
                  style: textTheme.bodyLarge?.copyWith(
                    color: PulseColors.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
