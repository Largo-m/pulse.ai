import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:screen_retriever/screen_retriever.dart';
import 'package:window_manager/window_manager.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (_isDesktop) {
    await windowManager.ensureInitialized();
    final display = await screenRetriever.getPrimaryDisplay();
    final initialSize = display.visibleSize ?? display.size;
    await windowManager.waitUntilReadyToShow(
      WindowOptions(
        size: initialSize,
        minimumSize: const Size(400, 300),
        center: false,
        title: 'pulse.ia',
        backgroundColor: Colors.transparent,
        titleBarStyle: TitleBarStyle.hidden,
        windowButtonVisibility: defaultTargetPlatform == TargetPlatform.macOS,
      ),
      () async {
        await windowManager.show();
        await windowManager.focus();
        await windowManager.maximize();
      },
    );
  }
  runApp(const MainApp());
}

bool get _isDesktop =>
    !kIsWeb &&
    (defaultTargetPlatform == TargetPlatform.windows ||
        defaultTargetPlatform == TargetPlatform.macOS ||
        defaultTargetPlatform == TargetPlatform.linux);

class MainApp extends StatelessWidget {
  const MainApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6366F1)),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6366F1),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      builder: (context, child) {
        final content = child ?? const SizedBox.shrink();
        if (_isDesktop) {
          return VirtualWindowFrameInit()(context, content);
        }
        return content;
      },
      home: const PulseShell(),
    );
  }
}

class PulseShell extends StatefulWidget {
  const PulseShell({super.key});

  @override
  State<PulseShell> createState() => _PulseShellState();
}

class _PulseShellState extends State<PulseShell> {
  bool _sidebarOpen = true;
  final GlobalKey<NavigatorState> _shellNavigatorKey =
      GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context) {
    final brightness = Theme.of(context).brightness;
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PulseTitleBar(
            brightness: brightness,
            sidebarOpen: _sidebarOpen,
            showWindowControls: _isDesktop,
            onSidebarToggle: () {
              setState(() => _sidebarOpen = !_sidebarOpen);
            },
          ),
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClipRect(
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    curve: Curves.easeInOut,
                    width: _sidebarOpen ? 240 : 0,
                    child: _sidebarOpen
                        ? Material(
                            color: Theme.of(
                              context,
                            ).colorScheme.surfaceContainerHighest,
                            child: ListView(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              children: [
                                ListTile(
                                  leading: Icon(
                                    Icons.dashboard_outlined,
                                    color: Theme.of(
                                      context,
                                    ).colorScheme.primary,
                                  ),
                                  title: const Text('Início'),
                                  onTap: () async {
                                    await _shellNavigatorKey.currentState
                                        ?.pushNamedAndRemoveUntil(
                                          '/',
                                          (route) => false,
                                        );
                                  },
                                ),
                              ],
                            ),
                          )
                        : const SizedBox.shrink(),
                  ),
                ),
                Expanded(
                  child: Navigator(
                    key: _shellNavigatorKey,
                    initialRoute: '/',
                    onGenerateRoute: (settings) {
                      switch (settings.name) {
                        case '/':
                          return MaterialPageRoute<void>(
                            builder: (_) => const HomeScreen(),
                            settings: settings,
                          );
                        default:
                          return MaterialPageRoute<void>(
                            builder: (_) => const HomeScreen(),
                            settings: settings,
                          );
                      }
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surface,
      child: Center(
        child: Text(
          'pulse.ia',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
      ),
    );
  }
}

class PulseTitleBar extends StatefulWidget {
  const PulseTitleBar({
    super.key,
    required this.brightness,
    required this.sidebarOpen,
    required this.showWindowControls,
    required this.onSidebarToggle,
  });

  final Brightness brightness;
  final bool sidebarOpen;
  final bool showWindowControls;
  final VoidCallback onSidebarToggle;

  @override
  State<PulseTitleBar> createState() => _PulseTitleBarState();
}

class _PulseTitleBarState extends State<PulseTitleBar> with WindowListener {
  @override
  void initState() {
    if (widget.showWindowControls) {
      windowManager.addListener(this);
    }
    super.initState();
  }

  @override
  void dispose() {
    if (widget.showWindowControls) {
      windowManager.removeListener(this);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final titleStyle = TextStyle(
      color: widget.brightness == Brightness.light
          ? Colors.black.withValues(alpha: 0.8956)
          : Colors.white,
      fontSize: 14,
      fontWeight: FontWeight.w600,
    );
    final titleWidget = IgnorePointer(
      child: Text('pulse.ia', style: titleStyle),
    );
    final sidebarButton = _SidebarToggleCaptionButton(
      brightness: widget.brightness,
      expanded: widget.sidebarOpen,
      onPressed: widget.onSidebarToggle,
    );
    final useNativeMacChrome =
        widget.showWindowControls &&
        defaultTargetPlatform == TargetPlatform.macOS;
    final sidebarLeftInset = useNativeMacChrome ? 78.0 : 8.0;

    Widget barBody;
    if (!widget.showWindowControls || useNativeMacChrome) {
      barBody = Stack(
        clipBehavior: Clip.none,
        fit: StackFit.expand,
        children: [
          DragToMoveArea(
            child: SizedBox.expand(child: Center(child: titleWidget)),
          ),
          Positioned(
            left: sidebarLeftInset,
            top: 0,
            bottom: 0,
            child: Center(child: sidebarButton),
          ),
        ],
      );
    } else {
      barBody = Stack(
        clipBehavior: Clip.none,
        fit: StackFit.expand,
        children: [
          DragToMoveArea(
            child: SizedBox.expand(child: Center(child: titleWidget)),
          ),
          Positioned(
            left: 8,
            top: 0,
            bottom: 0,
            child: Align(
              alignment: Alignment.centerLeft,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  sidebarButton,
                  WindowCaptionButton.close(
                    brightness: widget.brightness,
                    onPressed: () async{
                      await windowManager.close();
                    },
                  ),
                  WindowCaptionButton.minimize(
                    brightness: widget.brightness,
                    onPressed: () async {
                      final minimized = await windowManager.isMinimized();
                      if (minimized) {
                        await windowManager.restore();
                      } else {
                        await windowManager.minimize();
                      }
                    },
                  ),
                  FutureBuilder<bool>(
                    future: windowManager.isMaximized(),
                    builder: (context, snapshot) {
                      if (snapshot.data == true) {
                        return WindowCaptionButton.unmaximize(
                          brightness: widget.brightness,
                          onPressed: () async   {
                            await windowManager.unmaximize();
                          },
                        );
                      }
                      return WindowCaptionButton.maximize(
                        brightness: widget.brightness,
                        onPressed: () async {
                          await windowManager.maximize();
                        },
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      );
    }

    return Material(
      color: widget.brightness == Brightness.dark
          ? const Color(0xff1C1C1C)
          : Theme.of(context).colorScheme.surfaceContainerHighest,
      child: SizedBox(
        height: kWindowCaptionHeight,
        width: double.infinity,
        child: barBody,
      ),
    );
  }

  @override
  void onWindowMaximize() {
    setState(() {});
  }

  @override
  void onWindowUnmaximize() {
    setState(() {});
  }
}

class _SidebarToggleCaptionButton extends StatefulWidget {
  const _SidebarToggleCaptionButton({
    required this.brightness,
    required this.expanded,
    required this.onPressed,
  });

  final Brightness brightness;
  final bool expanded;
  final VoidCallback onPressed;

  @override
  State<_SidebarToggleCaptionButton> createState() =>
      _SidebarToggleCaptionButtonState();
}

class _SidebarToggleCaptionButtonState
    extends State<_SidebarToggleCaptionButton> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final isDark = widget.brightness == Brightness.dark;
    final iconColor = isDark
        ? Colors.white
        : Colors.black.withValues(alpha: 0.8956);
    const bgNormal = Colors.transparent;
    final bgHover = isDark
        ? Colors.white.withValues(alpha: 0.0605)
        : Colors.black.withValues(alpha: 0.0373);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onPressed,
        child: Container(
          constraints: const BoxConstraints(minWidth: 46, minHeight: 32),
          decoration: BoxDecoration(color: _hover ? bgHover : bgNormal),
          alignment: Alignment.center,
          child: Icon(
            widget.expanded ? Icons.view_sidebar : Icons.view_sidebar_outlined,
            size: 16,
            color: iconColor,
          ),
        ),
      ),
    );
  }
}
