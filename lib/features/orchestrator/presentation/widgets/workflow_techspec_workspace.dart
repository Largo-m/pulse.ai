import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_phase.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_archive_sidebar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_instruction_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_mapping_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_prd_required_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/workflow_techspec_gate.dart';

final class WorkflowTechspecWorkspace extends StatelessWidget {
  const WorkflowTechspecWorkspace({
    super.key,
    required this.workflowSlug,
    required this.prdPhaseStatus,
    required this.onInitialize,
    required this.onApplyInstruction,
  });

  final String workflowSlug;
  final PrdPhaseStatus prdPhaseStatus;
  final VoidCallback onInitialize;
  final VoidCallback onApplyInstruction;

  @override
  Widget build(BuildContext context) {
    final bool gated = isTechspecWorkspaceGated(prdPhaseStatus);
    final bool prdApproved = prdPhaseStatus == PrdPhaseStatus.approved;
    final Set<WorkflowPhase> completedPhases = prdApproved
        ? const <WorkflowPhase>{WorkflowPhase.prd}
        : const <WorkflowPhase>{};

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        WorkflowPhaseStepper(
          currentPhase: WorkflowPhase.techspec,
          completedPhases: completedPhases,
        ),
        Expanded(
          child: gated
              ? const WorkflowTechspecPrdRequiredBody()
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    Expanded(
                      child: WorkflowTechspecMappingBody(
                        onInitialize: onInitialize,
                      ),
                    ),
                    WorkflowArchiveSidebar(
                      artifactFileName:
                          OrchestratorStrings.workflowArchivePrdFileName(
                            workflowSlug,
                          ),
                      isApproved: prdApproved,
                    ),
                  ],
                ),
        ),
        if (!gated) WorkflowTechspecInstructionBar(onApply: onApplyInstruction),
      ],
    );
  }
}
