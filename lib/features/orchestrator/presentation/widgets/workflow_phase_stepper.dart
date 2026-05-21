import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_phase.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class WorkflowPhaseStepper extends StatelessWidget {
  const WorkflowPhaseStepper({
    super.key,
    required this.currentPhase,
    required this.completedPhases,
  });

  final WorkflowPhase currentPhase;
  final Set<WorkflowPhase> completedPhases;

  static const List<WorkflowPhase> _orderedPhases = <WorkflowPhase>[
    WorkflowPhase.prd,
    WorkflowPhase.techspec,
    WorkflowPhase.tasks,
    WorkflowPhase.qa,
    WorkflowPhase.review,
  ];

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return SizedBox(
      height: PulseDimensions.workflowStepperHeight,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: PulseColors.surfaceContainerLow.withValues(alpha: 0.5),
          border: const Border(
            bottom: BorderSide(color: PulseColors.outlineVariant),
          ),
        ),
        child: Padding(
          padding: PulseInsets.breadcrumbHorizontal,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: PulseDimensions.workflowStepperMaxWidth,
              ),
              child: Row(children: _buildStepChildren(textTheme)),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _buildStepChildren(TextTheme textTheme) {
    final List<Widget> children = <Widget>[];
    for (int index = 0; index < _orderedPhases.length; index++) {
      final WorkflowPhase phase = _orderedPhases[index];
      if (index > 0) {
        children.add(
          Expanded(
            child: _StepConnector(
              isActive:
                  completedPhases.contains(_orderedPhases[index - 1]) ||
                  phase == currentPhase,
            ),
          ),
        );
      }
      children.add(
        _WorkflowStepItem(
          label: _labelForPhase(phase),
          stepNumber: index + 1,
          isCompleted: completedPhases.contains(phase),
          isCurrent: phase == currentPhase,
          textTheme: textTheme,
        ),
      );
    }
    return children;
  }

  String _labelForPhase(WorkflowPhase phase) {
    return switch (phase) {
      WorkflowPhase.prd => OrchestratorStrings.workflowPhasePrd,
      WorkflowPhase.techspec => OrchestratorStrings.workflowPhaseTechspec,
      WorkflowPhase.tasks => OrchestratorStrings.workflowPhaseTasks,
      WorkflowPhase.qa => OrchestratorStrings.workflowPhaseQa,
      WorkflowPhase.review => OrchestratorStrings.workflowPhaseReview,
    };
  }
}

final class _StepConnector extends StatelessWidget {
  const _StepConnector({required this.isActive});

  final bool isActive;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: PulseDimensions.sectionGapMd,
      ),
      child: SizedBox(
        height: PulseDimensions.workflowStepConnectorHeight,
        child: ColoredBox(
          color: isActive
              ? PulseColors.tertiary.withValues(
                  alpha: PulseDimensions.workflowStepConnectorActiveAlpha,
                )
              : PulseColors.outlineVariant,
        ),
      ),
    );
  }
}

final class _WorkflowStepItem extends StatelessWidget {
  const _WorkflowStepItem({
    required this.label,
    required this.stepNumber,
    required this.isCompleted,
    required this.isCurrent,
    required this.textTheme,
  });

  final String label;
  final int stepNumber;
  final bool isCompleted;
  final bool isCurrent;
  final TextTheme textTheme;

  @override
  Widget build(BuildContext context) {
    final bool isFuture = !isCompleted && !isCurrent;
    final Widget indicator = _buildIndicator();
    final TextStyle labelStyle = (textTheme.labelMedium ?? const TextStyle())
        .copyWith(
          color: isCompleted
              ? PulseColors.primary
              : isCurrent
              ? PulseColors.primary
              : PulseColors.onSurface,
          fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
        );

    final Widget content = Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        indicator,
        const SizedBox(width: PulseDimensions.sectionGapSm),
        Text(label, style: labelStyle),
      ],
    );

    if (!isFuture) {
      return content;
    }

    return Opacity(
      opacity: PulseDimensions.workflowStepFutureOpacity,
      child: content,
    );
  }

  Widget _buildIndicator() {
    if (isCompleted) {
      return const SizedBox(
        width: PulseDimensions.workflowStepIndicatorSize,
        height: PulseDimensions.workflowStepIndicatorSize,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: PulseColors.primary,
            shape: BoxShape.circle,
          ),
          child: Icon(
            Icons.check,
            size: PulseDimensions.sidebarTreeIconSize,
            color: PulseColors.onPrimary,
          ),
        ),
      );
    }

    if (isCurrent) {
      return Container(
        width: PulseDimensions.workflowStepIndicatorSize,
        height: PulseDimensions.workflowStepIndicatorSize,
        decoration: BoxDecoration(
          color: PulseColors.primary,
          shape: BoxShape.circle,
          border: Border.all(
            color: PulseColors.primary,
            width: PulseDimensions.workflowStepRingWidth,
          ),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: PulseColors.primary.withValues(alpha: 0.2),
              blurRadius: 0,
              spreadRadius: PulseDimensions.workflowStepRingWidth,
            ),
          ],
        ),
        alignment: Alignment.center,
        child: Text(
          '$stepNumber',
          style: (textTheme.labelMedium ?? const TextStyle()).copyWith(
            color: PulseColors.onPrimary,
            fontWeight: FontWeight.w500,
          ),
        ),
      );
    }

    return Container(
      width: PulseDimensions.workflowStepIndicatorSize,
      height: PulseDimensions.workflowStepIndicatorSize,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: PulseColors.outline),
      ),
      alignment: Alignment.center,
      child: Text(
        '$stepNumber',
        style: (textTheme.labelMedium ?? const TextStyle()).copyWith(
          color: PulseColors.onSurface,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
