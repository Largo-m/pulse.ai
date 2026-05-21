import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdReviewActionBar extends StatelessWidget {
  const PrdReviewActionBar({
    super.key,
    required this.showsUserEditedBadge,
    required this.canSave,
    required this.canApprove,
    required this.canReject,
    required this.isSaving,
    required this.isApproving,
    required this.isRejecting,
    required this.onSave,
    required this.onApprove,
    required this.onReject,
  });

  final bool showsUserEditedBadge;
  final bool canSave;
  final bool canApprove;
  final bool canReject;
  final bool isSaving;
  final bool isApproving;
  final bool isRejecting;
  final VoidCallback onSave;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: const BoxDecoration(
        color: PulseColors.surfaceContainerLow,
        border: Border(top: BorderSide(color: PulseColors.outlineVariant)),
      ),
      child: Padding(
        padding: PulseInsets.prdReviewActionBar,
        child: Row(
          children: <Widget>[
            if (showsUserEditedBadge) ...<Widget>[
              Semantics(
                label: OrchestratorStrings.prdReviewUserEditedBadgeSemantics,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: PulseColors.tertiaryContainer,
                    borderRadius: BorderRadius.circular(
                      PulseRadii.workflowInstructionBar,
                    ),
                  ),
                  child: Padding(
                    padding: PulseInsets.prdReviewUserEditedBadge,
                    child: Text(
                      OrchestratorStrings.prdReviewUserEditedBadge,
                      style: textTheme.labelSmall?.copyWith(
                        color: PulseColors.onTertiaryContainer,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: PulseDimensions.sectionGapMd),
            ],
            const Spacer(),
            Semantics(
              button: true,
              enabled: canSave && !isSaving,
              label: OrchestratorStrings.prdReviewSaveDraftSemantics,
              child: OutlinedButton(
                onPressed: canSave && !isSaving ? onSave : null,
                child: const Text(OrchestratorStrings.prdReviewSaveDraftButton),
              ),
            ),
            const SizedBox(width: PulseDimensions.sectionGapSm),
            Semantics(
              button: true,
              enabled: canReject && !isRejecting,
              label: OrchestratorStrings.prdReviewRejectSemantics,
              child: OutlinedButton(
                onPressed: canReject && !isRejecting ? onReject : null,
                child: const Text(OrchestratorStrings.prdReviewRejectButton),
              ),
            ),
            const SizedBox(width: PulseDimensions.sectionGapSm),
            Semantics(
              button: true,
              enabled: canApprove && !isApproving,
              label: OrchestratorStrings.prdReviewApproveSemantics,
              child: FilledButton(
                onPressed: canApprove && !isApproving ? onApprove : null,
                child: const Text(OrchestratorStrings.prdReviewApproveButton),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
