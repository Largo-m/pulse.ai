import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdWorkflowStatusChip extends StatelessWidget {
  const PrdWorkflowStatusChip({super.key, required this.state});

  final PrdWorkflowState state;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final _ChipStyle style = _styleForStatus(state.phaseStatus);

    return Semantics(
      label: style.semanticsLabel,
      child: Container(
        height: PulseDimensions.workflowStreamChipHeight,
        padding: PulseInsets.workflowStreamChip,
        decoration: BoxDecoration(
          color: style.backgroundColor,
          borderRadius: BorderRadius.circular(PulseRadii.workflowStreamPanel),
          border: Border.all(color: style.borderColor),
        ),
        alignment: Alignment.center,
        child: Text(
          style.label,
          style: textTheme.labelMedium?.copyWith(
            color: style.foregroundColor,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  _ChipStyle _styleForStatus(PrdWorkflowPhaseUiStatus status) {
    return switch (status) {
      PrdWorkflowPhaseUiStatus.notStarted => const _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusNotStarted,
        semanticsLabel: OrchestratorStrings.prdWorkflowStatusNotStarted,
        backgroundColor: PulseColors.surfaceContainerLow,
        borderColor: PulseColors.outlineVariant,
        foregroundColor: PulseColors.onSurfaceVariant,
      ),
      PrdWorkflowPhaseUiStatus.running => _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusRunning,
        semanticsLabel:
            OrchestratorStrings.prdWorkflowRunStatusRunningSemantics,
        backgroundColor: PulseColors.primaryContainer,
        borderColor: PulseColors.primary.withValues(alpha: 0.3),
        foregroundColor: PulseColors.onPrimaryContainer,
      ),
      PrdWorkflowPhaseUiStatus.pendingApproval => _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusPendingApproval,
        semanticsLabel:
            OrchestratorStrings.prdWorkflowRunStatusPendingApprovalSemantics,
        backgroundColor: PulseColors.tertiaryContainer,
        borderColor: PulseColors.tertiary.withValues(alpha: 0.3),
        foregroundColor: PulseColors.onTertiaryContainer,
      ),
      PrdWorkflowPhaseUiStatus.approved => const _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusApproved,
        semanticsLabel: OrchestratorStrings.prdWorkflowStatusApproved,
        backgroundColor: PulseColors.tertiaryContainer,
        borderColor: PulseColors.tertiary,
        foregroundColor: PulseColors.onTertiaryContainer,
      ),
      PrdWorkflowPhaseUiStatus.failed => _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusFailed,
        semanticsLabel: OrchestratorStrings.prdWorkflowRunStatusFailedSemantics,
        backgroundColor: PulseColors.surfaceContainerHigh,
        borderColor: PulseColors.secondary.withValues(alpha: 0.4),
        foregroundColor: PulseColors.secondary,
      ),
      PrdWorkflowPhaseUiStatus.cancelled => const _ChipStyle(
        label: OrchestratorStrings.prdWorkflowStatusCancelled,
        semanticsLabel:
            OrchestratorStrings.prdWorkflowRunStatusCancelledSemantics,
        backgroundColor: PulseColors.surfaceContainerHigh,
        borderColor: PulseColors.outlineVariant,
        foregroundColor: PulseColors.onSurfaceVariant,
      ),
    };
  }
}

final class _ChipStyle {
  const _ChipStyle({
    required this.label,
    required this.semanticsLabel,
    required this.backgroundColor,
    required this.borderColor,
    required this.foregroundColor,
  });

  final String label;
  final String semanticsLabel;
  final Color backgroundColor;
  final Color borderColor;
  final Color foregroundColor;
}
