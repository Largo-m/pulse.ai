import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdReviewActionBar extends StatelessWidget {
  const PrdReviewActionBar({
    super.key,
    this.artifactMode = false,
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

  final bool artifactMode;
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
    final String rejectLabel = artifactMode
        ? OrchestratorStrings.prdArtifactRequestRevisionsButton
        : OrchestratorStrings.prdReviewRejectButton;
    final String approveLabel = artifactMode
        ? OrchestratorStrings.prdArtifactApproveButton
        : OrchestratorStrings.prdReviewApproveButton;

    if (artifactMode) {
      return Row(
        children: <Widget>[
          if (showsUserEditedBadge) ...<Widget>[
            _UserEditedBadge(textTheme: textTheme),
            const SizedBox(width: PulseDimensions.sectionGapMd),
          ],
          if (canSave) ...<Widget>[
            Semantics(
              button: true,
              enabled: canSave && !isSaving,
              label: OrchestratorStrings.prdReviewSaveDraftSemantics,
              child: TextButton(
                onPressed: canSave && !isSaving ? onSave : null,
                child: const Text(OrchestratorStrings.prdReviewSaveDraftButton),
              ),
            ),
            const Spacer(),
          ] else
            const Spacer(),
          Semantics(
            button: true,
            enabled: canReject && !isRejecting,
            label: OrchestratorStrings.prdReviewRejectSemantics,
            child: OutlinedButton(
              onPressed: canReject && !isRejecting ? onReject : null,
              style: OutlinedButton.styleFrom(
                foregroundColor: PulseColors.primary,
                side: const BorderSide(color: PulseColors.primary),
              ),
              child: Text(rejectLabel),
            ),
          ),
          const SizedBox(width: PulseDimensions.sectionGapSm),
          Semantics(
            button: true,
            enabled: canApprove && !isApproving,
            label: OrchestratorStrings.prdReviewApproveSemantics,
            child: FilledButton(
              onPressed: canApprove && !isApproving ? onApprove : null,
              child: Text(approveLabel),
            ),
          ),
        ],
      );
    }

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
              _UserEditedBadge(textTheme: textTheme),
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
                child: Text(rejectLabel),
              ),
            ),
            const SizedBox(width: PulseDimensions.sectionGapSm),
            Semantics(
              button: true,
              enabled: canApprove && !isApproving,
              label: OrchestratorStrings.prdReviewApproveSemantics,
              child: FilledButton(
                onPressed: canApprove && !isApproving ? onApprove : null,
                child: Text(approveLabel),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

final class _UserEditedBadge extends StatelessWidget {
  const _UserEditedBadge({required this.textTheme});

  final TextTheme textTheme;

  @override
  Widget build(BuildContext context) {
    return Semantics(
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
    );
  }
}
