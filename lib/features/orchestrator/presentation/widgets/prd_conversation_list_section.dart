import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_section_header.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdConversationListSection extends StatelessWidget {
  const PrdConversationListSection({super.key, required this.messages});

  final List<PrdConversationMessageUiModel> messages;

  @override
  Widget build(BuildContext context) {
    if (messages.isEmpty) {
      return const SizedBox.shrink();
    }

    return Semantics(
      container: true,
      label: OrchestratorStrings.prdWorkflowConversationSectionSemantics,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: PulseColors.surfaceContainer,
          borderRadius: BorderRadius.circular(PulseRadii.workflowStreamPanel),
          border: Border.all(
            color: PulseColors.outlineVariant,
            width: PulseDimensions.workflowStreamPanelBorderWidth,
          ),
        ),
        child: Padding(
          padding: PulseInsets.workflowStreamPanel,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              const WorkflowSectionHeader(
                icon: Icons.forum_outlined,
                title: OrchestratorStrings.prdWorkflowConversationSectionTitle,
              ),
              const SizedBox(height: PulseDimensions.sectionGapMd),
              ..._conversationTiles(context, messages),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _conversationTiles(
    BuildContext context,
    List<PrdConversationMessageUiModel> items,
  ) {
    final List<Widget> tiles = <Widget>[];
    for (int index = 0; index < items.length; index++) {
      if (index > 0) {
        tiles.add(const SizedBox(height: PulseDimensions.sectionGapMd));
      }
      tiles.add(_PrdConversationMessageTile(message: items[index]));
    }
    return tiles;
  }
}

final class _PrdConversationMessageTile extends StatelessWidget {
  const _PrdConversationMessageTile({required this.message});

  final PrdConversationMessageUiModel message;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final bool isUser = message.role == PrdConversationMessageRole.user;
    final String roleLabel = isUser
        ? OrchestratorStrings.prdWorkflowConversationUserRoleLabel
        : OrchestratorStrings.prdWorkflowConversationAgentRoleLabel;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth:
              MediaQuery.sizeOf(context).width *
              PulseDimensions.workflowUserBubbleMaxWidthFactor,
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: isUser
                ? PulseColors.surfaceContainerHigh
                : PulseColors.surfaceContainerLowest,
            borderRadius: BorderRadius.circular(PulseRadii.workflowUserBubble),
            border: Border.all(color: PulseColors.outlineVariant),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: PulseDimensions.sectionGapMd,
              vertical: PulseDimensions.sectionGapMd,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  roleLabel,
                  style: textTheme.labelSmall?.copyWith(
                    color: PulseColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: PulseDimensions.sectionGapSm),
                Text(
                  message.displayText,
                  style: textTheme.bodyMedium?.copyWith(
                    color: PulseColors.onSurface,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
