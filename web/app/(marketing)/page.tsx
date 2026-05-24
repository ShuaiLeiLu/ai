'use client';

import {
  ApartmentOutlined,
  AreaChartOutlined,
  ArrowRightOutlined,
  BookOutlined,
  CrownOutlined,
  GlobalOutlined,
  ReadOutlined,
  RobotOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Button, Col, Row, Typography } from 'antd';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

import { routes } from '@/lib/constants/routes';
import { Logo } from '@/components/ui/logo';

const { Title, Paragraph, Text } = Typography;

// Helper for consistent section styling
const SectionWrapper: FC<{ children: ReactNode; className?: string }> = ({ children, className = '' }) => (
  <section className={`relative w-full max-w-7xl mx-auto px-6 lg:px-8 py-24 md:py-32 ${className}`}>
    {children}
  </section>
);

// Glassmorphism Card Component - Redesigned for Premium Light Theme
const GlassCard: FC<{ icon: ReactNode; title: string; description: string }> = ({ icon, title, description }) => (
  <div className="group h-full p-8 rounded-3xl bg-white/70 backdrop-blur-xl border border-stone-200/50 shadow-sm transition-all duration-500 hover:border-[#1d4a34]/20 hover:bg-white hover:shadow-xl transform hover:-translate-y-2">
    <div className="flex flex-col h-full">
      <div className="mb-6 text-4xl text-[#1d4a34] group-hover:scale-110 transition-transform duration-500">{icon}</div>
      <h3 className="text-xl font-bold text-stone-850 mb-3 group-hover:text-[#1d4a34] transition-colors">{title}</h3>
      <p className="text-stone-500 text-[15px] leading-relaxed group-hover:text-stone-600 transition-colors">{description}</p>
    </div>
  </div>
);

// --- Page Sections ---

const HeroSection: FC = () => (
  <div className="relative h-[95vh] min-h-[700px] flex flex-col justify-center items-center overflow-hidden">
    {/* 背景网格装饰 */}
    <div className="absolute inset-0 z-0 opacity-40 [mask-image:radial-gradient(ellipse_at_center,black_70%,transparent_100%)]">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10 brightness-100"></div>
      <div className="h-full w-full bg-[linear-gradient(to_right,#00000008_1px,transparent_1px),linear-gradient(to_bottom,#00000008_1px,transparent_1px)] bg-[size:40px_40px]"></div>
    </div>

    <div className="z-10 px-4 text-center">
      <div className="flex justify-center mb-8 animate-fade-in-down">
        <div className="p-4 rounded-3xl bg-white/80 backdrop-blur-2xl border border-stone-200/50 shadow-xl">
          <Logo size={80} />
        </div>
      </div>
      
      <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#1d4a34]/10 border border-[#1d4a34]/20 text-[#1d4a34] text-xs font-semibold mb-6 animate-fade-in-down shadow-[0_4px_12px_rgba(29,74,52,0.06)]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#1d4a34]/40 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-[#1d4a34]"></span>
        </span>
        AI 原生自驱投研 OS 1.0 正式发布
      </div>

      <h1 className="text-5xl md:text-8xl font-black tracking-tight text-stone-850 mb-8 animate-fade-in-down">
        极睿<span className="text-transparent bg-clip-text bg-gradient-to-r from-[#1d4a34] to-[#2e5a44]">智投</span>
      </h1>
      
      <p className="max-w-2xl mx-auto text-lg md:text-xl text-stone-500 mb-12 animate-fade-in-up leading-relaxed">
        X-Insight：深度重构投研范式。通过 AI 智元自驱运行与海量数据穿透，
        为追求卓越收益的投资者提供机构级的决策进化引擎。
      </p>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-6 animate-fade-in-up">
        <Link href={routes.workstation}>
          <Button
            type="primary"
            size="large"
            className="!h-16 !px-12 !text-lg !bg-[#1d4a34] !border-none !rounded-full !font-bold !shadow-[0_10px_25px_rgba(29,74,52,0.2)] hover:!bg-[#2e5a44] transition-all duration-500 transform hover:scale-105"
          >
            开始智投之旅 <ArrowRightOutlined className="ml-2" />
          </Button>
        </Link>
        <div className="flex items-center gap-4 px-6 py-3 rounded-full border border-stone-200/60 bg-white/70 text-stone-500 hover:text-stone-800 transition-colors cursor-pointer shadow-sm hover:shadow-md">
          <span className="text-sm font-medium">查看架构白皮书</span>
          <div className="w-1.5 h-1.5 rounded-full bg-stone-300"></div>
          <span className="text-xs">v1.0.4</span>
        </div>
      </div>
    </div>
    
    {/* 底部渐变遮罩 */}
    <div className="absolute bottom-0 left-0 w-full h-32 bg-gradient-to-t from-[#faf9f6] to-transparent"></div>
  </div>
);

const FeaturesSection: FC = () => {
  const features = [
    {
      icon: <RobotOutlined />,
      title: 'AI 研究员智元',
      description: '基于多模态大模型的自驱研究员，7x24 小时透视全球市场，自动生成深度研报。',
    },
    {
      icon: <BookOutlined />,
      title: '知识资产中心',
      description: '结构化沉淀投研复盘数据，构建属于您的私有金融知识库与策略索引。',
    },
    {
      icon: <ApartmentOutlined />,
      title: '极速工作流编排',
      description: '通过可视化低代码界面，一键串联资讯获取、异动分析与风控预警。',
    },
    {
      icon: <AreaChartOutlined />,
      title: '盘前全景洞察',
      description: '在开盘前 15 分钟，AI 自动完成全市场情绪建模，锁定当日核心主线。',
    },
    {
      icon: <ReadOutlined />,
      title: '全量资讯穿透',
      description: '穿透市场噪音，实时提取有效增量信息，自动关联板块逻辑与个股影响。',
    },
    {
      icon: <StockOutlined />,
      title: '策略演化实验室',
      description: '在实战级环境中进行策略仿真回测，通过 AI 动态参数优化，寻找阿尔法。',
    },
  ];

  return (
    <SectionWrapper>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-20 gap-8">
        <div className="max-w-2xl">
          <h2 className="text-4xl md:text-6xl font-bold text-stone-850 leading-tight">核心引擎</h2>
          <p className="text-xl text-stone-500 mt-6">
            从宏观叙事到微观异动，X-Insight 提供覆盖投研全生命周期的 AI 工具矩阵。
          </p>
        </div>
        <div className="hidden md:block">
           <div className="text-[#1d4a34] font-mono text-sm tracking-widest uppercase font-semibold">Technology Stack</div>
           <div className="h-1 w-24 bg-[#1d4a34] mt-2"></div>
        </div>
      </div>
      <Row gutter={[32, 32]}>
        {features.map((feature) => (
          <Col key={feature.title} xs={24} sm={12} lg={8}>
            <GlassCard {...feature} />
          </Col>
        ))}
      </Row>
    </SectionWrapper>
  );
};

const SystemsSection: FC = () => (
  <SectionWrapper>
    <div className="grid md:grid-cols-2 gap-8 items-stretch">
      <div className="group relative overflow-hidden bg-white/70 backdrop-blur-xl p-12 rounded-3xl border border-stone-200/50 shadow-md hover:border-[#1d4a34]/15 hover:shadow-xl transition-all duration-700">
        <div className="absolute -right-20 -top-20 w-64 h-64 bg-amber-500/[0.03] rounded-full blur-[100px] group-hover:bg-amber-500/10 transition-colors"></div>
        <div className="relative z-10">
          <ThunderboltOutlined className="text-6xl text-amber-500 mb-8" />
          <h2 className="text-4xl font-bold text-stone-850 mb-6">算力能源系统</h2>
          <p className="text-stone-500 text-lg leading-relaxed">
            “极睿算力”是驱动智元核心的底层能源。每次深度分析、高频监控或研报生成都需消耗算力。我们提供多维补给机制，确保您的 AI 研究引擎时刻保持投研计算的巅峰性能。
          </p>
        </div>
      </div>
      
      <div className="group relative overflow-hidden bg-white/70 backdrop-blur-xl p-12 rounded-3xl border border-stone-200/50 shadow-md hover:border-[#1d4a34]/15 hover:shadow-xl transition-all duration-700">
        <div className="absolute -right-20 -top-20 w-64 h-64 bg-[#1d4a34]/[0.03] rounded-full blur-[100px] group-hover:bg-[#1d4a34]/10 transition-colors"></div>
        <div className="relative z-10">
          <CrownOutlined className="text-6xl text-[#1d4a34] mb-8" />
          <h2 className="text-4xl font-bold text-stone-850 mb-6">智投会员体系</h2>
          <p className="text-stone-500 text-lg leading-relaxed">
            从基础版到黑金级专业版，阶梯式解锁更强大的 AI 模型权限、更低的延迟响应以及无限次的专家级投研任务，满足从个人投资者到专业机构的全方位需求。
          </p>
        </div>
      </div>
    </div>
  </SectionWrapper>
);

const CallToActionSection: FC = () => (
  <SectionWrapper>
    <div className="relative overflow-hidden text-center bg-gradient-to-br from-[#faf9f6]/80 to-[#e8e2d5]/60 p-16 md:p-24 rounded-[3rem] border border-stone-200/50 shadow-lg backdrop-blur-md">
      {/* 背景光斑 */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-[radial-gradient(circle_at_50%_50%,rgba(29,74,52,0.05),transparent_70%)]"></div>
      
      <div className="relative z-10">
        <div className="mb-10 inline-block p-5 rounded-2xl bg-white/80 border border-stone-200/50 shadow-sm">
           <GlobalOutlined className="text-5xl text-[#1d4a34]" />
        </div>
        <h2 className="text-4xl md:text-6xl font-bold text-stone-850 mb-8">准备好拥抱 AI 投研新纪元了吗？</h2>
        <p className="text-xl text-stone-500 mt-4 max-w-2xl mx-auto mb-12">
          加入极睿智投，与全球 50,000+ 投资者共同进化的自驱数据智慧。
        </p>
        <Link href={routes.workstation}>
          <Button
            type="primary"
            size="large"
            className="!h-16 !px-12 !text-lg !bg-[#1d4a34] !text-white !font-bold !border-none !rounded-full !shadow-[0_15px_30px_rgba(29,74,52,0.2)] hover:!bg-[#2e5a44] hover:!scale-105 transition-all duration-500"
          >
            免费开启 14天专业版试用
          </Button>
        </Link>
      </div>
    </div>
  </SectionWrapper>
);

// --- Main Page Component ---

export default function MarketingHomePage() {
  return (
    <>
      <div className="min-h-screen bg-gradient-to-b from-[#faf9f6] via-[#f5f2e9] to-[#eae5d8] text-stone-800 selection:bg-[#1d4a34]/10 selection:text-[#1d4a34]">
        {/* 动态渐变背景 */}
        <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] bg-[#1d4a34]/5 rounded-full blur-[120px] animate-blob-1"></div>
          <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-[#2e5a44]/5 rounded-full blur-[120px] animate-blob-2"></div>
        </div>

        <main className="relative z-10">
          <HeroSection />
          <FeaturesSection />
          <SystemsSection />
          <CallToActionSection />
          
          <footer className="py-12 border-t border-stone-200/50 text-center">
             <div className="flex justify-center mb-6">
                <Logo size={24} className="grayscale opacity-40" />
              </div>
             <p className="text-stone-400 text-sm italic font-serif">
                &copy; {new Date().getFullYear()} X-Insight (极睿智投). All rights reserved. Precision in Every Decision.
             </p>
          </footer>
        </main>
      </div>

      <style jsx global>{`
        @keyframes fade-in-down {
          from {
            opacity: 0;
            transform: translateY(-30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in-down {
          animation: fade-in-down 1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
        }
        .animate-fade-in-up {
          animation: fade-in-up 1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
        }

        @keyframes blob-1-anim {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(30px, 40px) scale(1.1); }
        }
        @keyframes blob-2-anim {
          0%, 100% { transform: translate(0, 0) scale(1.1); }
          50% { transform: translate(-30px, -40px) scale(1); }
        }
        .animate-blob-1 {
          animation: blob-1-anim 15s infinite ease-in-out;
        }
        .animate-blob-2 {
          animation: blob-2-anim 18s infinite ease-in-out;
        }
      `}</style>
    </>
  );
}
