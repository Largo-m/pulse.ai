import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowTerminalLog extends StatelessWidget {
  const WorkflowTerminalLog({
    super.key,
    required this.lines,
    this.emptyMessage = OrchestratorStrings.prdWorkflowStreamEmpty,
    this.placeholderLines = const <String>[],
  });

  final List<PrdStreamLineUiModel> lines;
  final String emptyMessage;
  final List<String> placeholderLines;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final TextStyle monoBase = (textTheme.labelMedium ?? const TextStyle())
        .copyWith(
          color: PulseColors.onSurface,
          height: PulseDimensions.workflowTerminalLineHeight / 11,
        );

    return DecoratedBox(
      decoration: BoxDecoration(
        color: PulseColors.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(PulseRadii.workflowTerminal),
        border: Border.all(color: PulseColors.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(PulseDimensions.sectionGapMd),
        child: lines.isEmpty && placeholderLines.isEmpty
            ? Center(
                child: Text(
                  emptyMessage,
                  style: textTheme.bodyMedium?.copyWith(
                    color: PulseColors.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              )
            : ListView.separated(
                itemCount: lines.isEmpty
                    ? placeholderLines.length
                    : lines.length,
                separatorBuilder: (BuildContext context, int index) {
                  return const SizedBox(
                    height: PulseDimensions.workflowStreamLineHeight / 2,
                  );
                },
                itemBuilder: (BuildContext context, int index) {
                  if (lines.isEmpty) {
                    return _TerminalLine(
                      text: placeholderLines[index],
                      style: monoBase,
                    );
                  }
                  final PrdStreamLineUiModel line = lines[index];
                  return _TerminalLine(text: line.displayText, style: monoBase);
                },
              ),
      ),
    );
  }
}

final class WorkflowTaggedTerminalLog extends StatelessWidget {
  const WorkflowTaggedTerminalLog({super.key, required this.entries});

  final List<WorkflowTerminalLogEntry> entries;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final TextStyle monoBase = (textTheme.labelMedium ?? const TextStyle())
        .copyWith(
          color: PulseColors.onSurface,
          height: PulseDimensions.workflowTerminalLineHeight / 11,
        );
    final TextStyle tagStyle = monoBase.copyWith(color: PulseColors.tertiary);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: PulseColors.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(PulseRadii.workflowTerminal),
        border: Border.all(color: PulseColors.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(PulseDimensions.sectionGapMd),
        child: ListView.separated(
          itemCount: entries.length,
          separatorBuilder: (BuildContext context, int index) {
            return const SizedBox(
              height: PulseDimensions.workflowStreamLineHeight / 2,
            );
          },
          itemBuilder: (BuildContext context, int index) {
            final WorkflowTerminalLogEntry entry = entries[index];
            return RichText(
              text: TextSpan(
                style: monoBase,
                children: <TextSpan>[
                  TextSpan(text: '> ', style: monoBase),
                  TextSpan(text: entry.tag, style: tagStyle),
                  TextSpan(text: ' ${entry.message}'),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

final class WorkflowTerminalLogEntry {
  const WorkflowTerminalLogEntry({required this.tag, required this.message});

  final String tag;
  final String message;
}

final class _TerminalLine extends StatelessWidget {
  const _TerminalLine({required this.text, required this.style});

  final String text;
  final TextStyle style;

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        style: style,
        children: <TextSpan>[
          TextSpan(text: '> ', style: style),
          TextSpan(text: text),
        ],
      ),
    );
  }
}
