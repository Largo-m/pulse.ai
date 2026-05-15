import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:pulse_ai/app/di/orchestrator_composition.dart';
import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/app/router/shell_navigator_routes.dart';
import 'package:pulse_ai/shared/strings/app_strings.dart';
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
        title: AppStrings.windowTitle,
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
      home: const OrchestratorCompositionScope(child: PulseShell()),
    );
  }
}

class PulseShell extends StatefulWidget {
  const PulseShell({super.key});

  @override
  State<PulseShell> createState() => _PulseShellState();
}

class _PulseShellState extends State<PulseShell> {
  @override
  Widget build(BuildContext context) {
    final brightness = Theme.of(context).brightness;
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PulseTitleBar(brightness: brightness, showWindowControls: _isDesktop),
          Expanded(
            child: Navigator(
              initialRoute: RoutePaths.orchestrator,
              onGenerateRoute: (RouteSettings settings) {
                if (settings.name == RoutePaths.home) {
                  return MaterialPageRoute<void>(
                    settings: settings,
                    builder: (BuildContext context) => const HomeScreen(),
                  );
                }
                return ShellNavigatorRoutes.onGenerateRoute(settings);
              },
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
          AppStrings.homeTitle,
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
    required this.showWindowControls,
  });

  final Brightness brightness;
  final bool showWindowControls;

  @override
  State<PulseTitleBar> createState() => _PulseTitleBarState();
}

class _PulseTitleBarState extends State<PulseTitleBar> with WindowListener {
  late final ValueNotifier<int> _windowLayoutTick;

  @override
  void initState() {
    super.initState();
    _windowLayoutTick = ValueNotifier<int>(0);
    if (widget.showWindowControls) {
      windowManager.addListener(this);
    }
  }

  @override
  void dispose() {
    _windowLayoutTick.dispose();
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
      child: Text(AppStrings.windowTitle, style: titleStyle),
    );
    final useNativeMacChrome =
        widget.showWindowControls &&
        defaultTargetPlatform == TargetPlatform.macOS;

    Widget barBody;
    if (!widget.showWindowControls || useNativeMacChrome) {
      barBody = DragToMoveArea(
        child: SizedBox.expand(child: Center(child: titleWidget)),
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
                  WindowCaptionButton.close(
                    brightness: widget.brightness,
                    onPressed: () async {
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
                  ValueListenableBuilder<int>(
                    valueListenable: _windowLayoutTick,
                    builder: (BuildContext context, int tick, Widget? child) {
                      return FutureBuilder<bool>(
                        future: windowManager.isMaximized(),
                        builder: (context, snapshot) {
                          if (snapshot.data == true) {
                            return WindowCaptionButton.unmaximize(
                              brightness: widget.brightness,
                              onPressed: () async {
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
    _windowLayoutTick.value++;
  }

  @override
  void onWindowUnmaximize() {
    _windowLayoutTick.value++;
  }
}
