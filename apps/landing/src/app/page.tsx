"use client";

import { motion } from "framer-motion";
import { 
  Terminal, 
  Cpu, 
  Zap, 
  Shield, 
  Layers, 
  Workflow,
  Github,
  ArrowRight
} from "lucide-react";
import { useState, useEffect } from "react";

// --- Components ---

const Navbar = () => {
  const handleNotImplemented = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    alert("该功能正在紧锣密鼓地开发中，敬请期待！");
  };

  return (
    <nav className="fixed top-0 w-full z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-foreground rounded-sm flex items-center justify-center">
            <span className="font-serif font-bold text-background text-xl">悟</span>
          </div>
          <span className="font-serif font-bold text-2xl tracking-widest">WUKONG</span>
        </div>
        <div className="hidden md:flex items-center gap-10 text-sm font-medium text-secondary">
          <a href="#features" className="hover:text-foreground transition-colors tracking-widest">特性</a>
          <a href="#terminal" onClick={handleNotImplemented} className="hover:text-foreground transition-colors tracking-widest">演示</a>
          <a href="#docs" onClick={handleNotImplemented} className="hover:text-foreground transition-colors tracking-widest">文档</a>
        </div>
        <div className="flex items-center gap-6">
          <a href="https://github.com/fangcircle2-jpg/wukong" target="_blank" rel="noreferrer" className="text-foreground hover:text-primary transition-colors">
            <Github size={22} strokeWidth={1.5} />
          </a>
          <a href="https://github.com/fangcircle2-jpg/wukong#readme" className="border border-foreground text-foreground px-5 py-2.5 text-sm font-medium hover:bg-foreground hover:text-background transition-all duration-300">
            立即开始
          </a>
        </div>
      </div>
    </nav>
  );
};

const TerminalWindow = () => {
  const [lines, setLines] = useState<string[]>([]);
  const [isTyping, setIsTyping] = useState(true);
  
  // 模拟一个实际的代码重构场景
  const fullText = [
    { text: "wukong refactor @src/auth.ts", type: "command", delay: 800 },
    { text: "Initializing Wukong Agent...", type: "system", delay: 600 },
    { text: "Analyzing context from @src/auth.ts...", type: "system", delay: 1200 },
    { text: "Found legacy JWT implementation. Planning refactor...", type: "system", delay: 1500 },
    { text: "Plan:", type: "accent", delay: 500 },
    { text: "  1. Migrate to NextAuth.js v5", type: "accent", delay: 400 },
    { text: "  2. Update session callbacks", type: "accent", delay: 400 },
    { text: "  3. Generate type definitions", type: "accent", delay: 400 },
    { text: "Executing batch operations...", type: "system", delay: 1500 },
    { text: "✓ Updated dependencies in package.json", type: "success", delay: 800 },
    { text: "✓ Rewrote src/auth.ts", type: "success", delay: 1200 },
    { text: "Refactor completed in 4.2s. View diff with `git diff`.", type: "primary", delay: 1000 }
  ];

  useEffect(() => {
    let currentLine = 0;
    let timeoutId: NodeJS.Timeout;

    const typeNextLine = () => {
      if (currentLine < fullText.length) {
        const line = fullText[currentLine];
        setLines(prev => [...prev, line.text]);
        currentLine++;
        
        if (currentLine < fullText.length) {
          timeoutId = setTimeout(typeNextLine, fullText[currentLine].delay);
        } else {
          setIsTyping(false);
        }
      }
    };

    // 初始延迟后开始打字
    timeoutId = setTimeout(typeNextLine, 1000);

    return () => clearTimeout(timeoutId);
  }, []);

  const getLineColor = (text: string) => {
    if (text.startsWith("wukong")) return "text-foreground font-medium";
    if (text.startsWith("Plan:") || text.startsWith("  ")) return "text-accent";
    if (text.startsWith("✓")) return "text-primary";
    if (text.startsWith("Refactor")) return "text-foreground font-bold";
    return "text-secondary";
  };

  return (
    <div className="w-full max-w-2xl mx-auto mt-24 bg-surface border border-border p-8 shadow-2xl shadow-black/5 font-mono text-sm leading-relaxed relative">
      <div className="absolute top-0 left-0 w-full h-1 bg-primary/20" />
      <div className="flex justify-between items-center mb-8 pb-4 border-b border-border/50">
        <div className="text-xs text-secondary tracking-widest uppercase">wukong — bash</div>
        <div className="flex gap-2">
          <div className="w-2 h-2 rounded-full bg-border" />
          <div className="w-2 h-2 rounded-full bg-border" />
          <div className="w-2 h-2 rounded-full bg-border" />
        </div>
      </div>
      <div className="min-h-[320px] text-foreground/80 flex flex-col justify-end">
        <div className="space-y-2">
          {lines.map((line, i) => (
            <motion.div 
              key={i} 
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="flex gap-4"
            >
              <span className="text-secondary/30 select-none w-4 text-right shrink-0">{i + 1}</span>
              <span className={getLineColor(line)}>
                {line.startsWith("wukong") ? "$ " : ""}
                {line}
              </span>
            </motion.div>
          ))}
          {isTyping && (
            <div className="flex gap-4">
              <span className="text-secondary/30 select-none w-4 text-right shrink-0">{lines.length + 1}</span>
              <motion.div 
                animate={{ opacity: [0, 1, 0] }} 
                transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                className="w-2 h-4 bg-primary translate-y-0.5"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const FeatureCard = ({ icon: Icon, title, desc, number }: { icon: any, title: string, desc: string, number: string }) => (
  <motion.div 
    whileHover={{ y: -5 }}
    className="p-10 border border-border bg-surface/50 hover:bg-surface transition-all group relative overflow-hidden"
  >
    <div className="absolute top-6 right-8 text-5xl font-serif font-bold text-border/30 group-hover:text-primary/10 transition-colors">
      {number}
    </div>
    <div className="mb-8 relative z-10">
      <Icon className="text-primary" size={28} strokeWidth={1.5} />
    </div>
    <h3 className="text-2xl font-serif font-bold mb-4 text-foreground relative z-10">{title}</h3>
    <p className="text-secondary leading-relaxed relative z-10">{desc}</p>
  </motion.div>
);

// --- Main Page ---

export default function LandingPage() {
  return (
    <main className="min-h-screen pt-20 selection:bg-primary/20 selection:text-primary">
      <Navbar />
      
      {/* Hero Section */}
      <section className="relative px-6 pt-32 pb-40 overflow-hidden flex flex-col items-center justify-center min-h-[90vh]">
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <div className="flex items-center justify-center gap-4 mb-10">
              <div className="h-px w-12 bg-primary/40" />
              <span className="text-primary text-sm font-medium tracking-[0.2em] uppercase">
                Alpha Version 0.1.0
              </span>
              <div className="h-px w-12 bg-primary/40" />
            </div>
            
            <h1 className="text-6xl md:text-8xl font-serif font-bold tracking-tight mb-8 text-foreground leading-[1.1] text-balance">
              如意金箍，<br className="hidden md:block" />
              <span className="italic font-light text-primary">随心而动</span>
            </h1>
            
            <div className="text-xl text-secondary max-w-2xl mx-auto mb-16 leading-relaxed text-balance space-y-4">
              <p>
                「悟空」取自齐天大圣，寓意灵动、变化与无所不能。它不仅是一个命令行工具，更是你终端里的七十二变。
              </p>
              <p className="text-base text-secondary/80">
                站在 <span className="font-mono text-foreground/80">Claude Code</span> 与 <span className="font-mono text-foreground/80">OpenDevin</span> 的肩膀上，我们致力于打造更懂中文开发者、更具扩展性的本地 AI Agent 引擎。
              </p>
            </div>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
              <a href="https://github.com/fangcircle2-jpg/wukong#快速开始" className="w-full sm:w-auto bg-foreground text-background px-10 py-4 text-sm font-bold tracking-widest hover:bg-primary transition-colors flex items-center justify-center gap-3">
                立即安装 <ArrowRight size={16} />
              </a>
              <a href="https://github.com/fangcircle2-jpg/wukong" target="_blank" rel="noreferrer" className="w-full sm:w-auto border border-border px-10 py-4 text-sm font-bold tracking-widest hover:bg-surface transition-colors flex items-center justify-center gap-3">
                查看源码
              </a>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 1, ease: "easeOut" }}
          >
            <TerminalWindow />
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-40 px-6 bg-surface/30 border-y border-border">
        <div className="max-w-6xl mx-auto">
          <div className="mb-24 md:flex justify-between items-end">
            <div className="max-w-2xl">
              <div className="flex items-center gap-4 mb-6">
                <div className="h-px w-8 bg-primary/40" />
                <span className="text-primary text-sm font-medium tracking-[0.2em] uppercase">核心特性</span>
              </div>
              <h2 className="text-4xl md:text-5xl font-serif font-bold text-foreground leading-tight text-balance">
                不仅仅是对话，<br />更是你的自动化执行引擎。
              </h2>
            </div>
            <p className="text-secondary mt-8 md:mt-0 max-w-xs text-balance">
              通过优雅的架构和强大的执行力，重新定义终端开发体验。
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
            <FeatureCard 
              number="01"
              icon={Cpu} 
              title="多模型适配" 
              desc="无缝切换 OpenAI, Claude, Gemini 以及本地 Llama 模型。不被任何供应商绑定。"
            />
            <FeatureCard 
              number="02"
              icon={Layers} 
              title="智能上下文" 
              desc="通过 @file, @url, @code 快速注入项目背景，让 AI 真正理解你的代码库。"
            />
            <FeatureCard 
              number="03"
              icon={Zap} 
              title="并行任务执行" 
              desc="独创 Batch 模式，支持多任务同时分发与处理，效率提升 300% 以上。"
            />
            <FeatureCard 
              number="04"
              icon={Workflow} 
              title="ReAct 智能循环" 
              desc="具备自主推理能力，能够自动拆解复杂任务、调用工具并根据反馈调整策略。"
            />
            <FeatureCard 
              number="05"
              icon={Shield} 
              title="安全沙箱" 
              desc="支持在 Docker 容器中执行敏感命令，保护你的宿主机系统安全。"
            />
            <FeatureCard 
              number="06"
              icon={Terminal} 
              title="极客终端体验" 
              desc="基于 Rich 构建的精美 UI，支持 Markdown 渲染、语法高亮与实时思考展示。"
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-20 px-6 bg-background">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-10">
          <div className="flex flex-col items-center md:items-start gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-foreground rounded-sm flex items-center justify-center">
                <span className="font-serif font-bold text-background">悟</span>
              </div>
              <span className="font-serif font-bold tracking-widest text-foreground">WUKONG</span>
            </div>
            <p className="text-secondary text-sm">© 2026 Wukong Contributors. Open Source.</p>
          </div>
          
          <div className="flex items-center gap-8 text-sm font-medium tracking-widest uppercase">
            <a href="https://github.com/fangcircle2-jpg/wukong" target="_blank" rel="noreferrer" className="text-secondary hover:text-foreground transition-colors">GitHub</a>
            <a href="#docs" onClick={(e) => { e.preventDefault(); alert("文档正在编写中，敬请期待！"); }} className="text-secondary hover:text-foreground transition-colors">文档</a>
            <a href="https://github.com/fangcircle2-jpg/wukong/issues" target="_blank" rel="noreferrer" className="text-secondary hover:text-foreground transition-colors">反馈</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
