import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_preserving_text.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowTerminalLog extends StatefulWidget {
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
  State<WorkflowTerminalLog> createState() => _WorkflowTerminalLogState();
}

final class _WorkflowTerminalLogState extends State<WorkflowTerminalLog> {
  final ScrollController _scrollController = ScrollController();

  @override
  void didUpdateWidget(WorkflowTerminalLog oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.lines.length != widget.lines.length) {
      _scrollToEnd();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) {
        return;
      }
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
    });
  }

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
        child: widget.lines.isEmpty && widget.placeholderLines.isEmpty
            ? Center(
                child: Text(
                  widget.emptyMessage,
                  style: textTheme.bodyMedium?.copyWith(
                    color: PulseColors.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              )
            : ListView.separated(
                controller: _scrollController,
                itemCount: widget.lines.isEmpty
                    ? widget.placeholderLines.length
                    : widget.lines.length,
                separatorBuilder: (BuildContext context, int index) {
                  return const SizedBox(
                    height: PulseDimensions.workflowStreamLineHeight / 2,
                  );
                },
                itemBuilder: (BuildContext context, int index) {
                  if (widget.lines.isEmpty) {
                    return _TerminalLine(
                      text: widget.placeholderLines[index],
                      style: monoBase,
                    );
                  }
                  final PrdStreamLineUiModel line = widget.lines[index];
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('> ', style: style),
        Expanded(
          child: WorkflowPreservingText(text: text, style: style),
        ),
      ],
    );
  }
}
