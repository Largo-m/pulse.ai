import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/utils/workflow_progress_calculator.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_progress_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_section_header.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_terminal_log.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class WorkflowTechspecMappingBody extends StatelessWidget {
  const WorkflowTechspecMappingBody({super.key, required this.onInitialize});

  final VoidCallback onInitialize;

  static const int _mappingProgressPercent = 45;

  static const List<WorkflowTerminalLogEntry> _placeholderEntries =
      <WorkflowTerminalLogEntry>[
        WorkflowTerminalLogEntry(
          tag: '[INIT]',
          message: 'Carregando requisitos do PRD aprovado…',
        ),
        WorkflowTerminalLogEntry(
          tag: '[STACK]',
          message: 'Inferindo camadas de domínio, dados e apresentação…',
        ),
        WorkflowTerminalLogEntry(
          tag: '[SCHEMA]',
          message: 'Mapeando entidades e contratos de repositório…',
        ),
        WorkflowTerminalLogEntry(
          tag: '[MAPPING]',
          message: 'Gerando diagrama de dependências entre módulos…',
        ),
      ];

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return SingleChildScrollView(
      padding: PulseInsets.pageScroll,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: PulseDimensions.workflowFeedMaxWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              WorkflowSectionHeader(
                icon: Icons.terminal,
                title: OrchestratorStrings.workflowTechspecMappingTitle,
                trailing: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: <Widget>[
                    Text(
                      workflowTechspecCompletionLabel(_mappingProgressPercent),
                      style: (textTheme.labelMedium ?? const TextStyle())
                          .copyWith(
                            color: PulseColors.primary,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: PulseDimensions.sectionGapSm),
                    const WorkflowProgressBar(percent: _mappingProgressPercent),
                  ],
                ),
              ),
              const SizedBox(height: PulseDimensions.sectionGapSm),
              Text(
                OrchestratorStrings.workflowTechspecMappingSubtitle,
                style: textTheme.bodyMedium?.copyWith(
                  color: PulseColors.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: PulseDimensions.sectionGapLg),
              const SizedBox(
                height: PulseDimensions.workflowTerminalMinHeight,
                child: WorkflowTaggedTerminalLog(entries: _placeholderEntries),
              ),
              const SizedBox(height: PulseDimensions.sectionGapLg),
              Align(
                alignment: Alignment.center,
                child: TextButton.icon(
                  onPressed: onInitialize,
                  icon: const Icon(Icons.play_arrow_outlined),
                  label: const Text(
                    OrchestratorStrings.workflowTechspecInitializeButton,
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
