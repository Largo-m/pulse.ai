import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_phase.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_init_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_instruction_bar.dart';

final class WorkflowTechspecWorkspace extends StatelessWidget {
  const WorkflowTechspecWorkspace({
    super.key,
    required this.onInitialize,
    required this.onApplyInstruction,
  });

  final VoidCallback onInitialize;
  final VoidCallback onApplyInstruction;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        const WorkflowPhaseStepper(
          currentPhase: WorkflowPhase.techspec,
          completedPhases: <WorkflowPhase>{WorkflowPhase.prd},
        ),
        Expanded(child: WorkflowTechspecInitBody(onInitialize: onInitialize)),
        WorkflowTechspecInstructionBar(onApply: onApplyInstruction),
      ],
    );
  }
}
