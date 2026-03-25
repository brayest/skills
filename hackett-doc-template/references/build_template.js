const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat, ImageRun,
  TabStopType, TabStopPosition
} = require("docx");

// ── HACKETT GROUP BRAND COLORS ─────────────────────────────────────────
const NAVY = "003366";       // Primary brand color
const TEXT2 = "44546A";      // Secondary heading color (Heading 2)
const TABLE_BORDER = "999999";
const WHITE = "FFFFFF";
const GRAY_BG = "F2F2F2";

// Risk colors (kept from original)
const RED_BG = "FFC7CE";   const RED_TEXT = "9C0006";
const ORANGE_BG = "FFE0B2"; const ORANGE_TEXT = "7A4100";
const YELLOW_BG = "FFF9C4"; const YELLOW_TEXT = "7A6500";
const GREEN_BG = "C6EFCE";  const GREEN_TEXT = "006100";
const BLUE_LIGHT = "D6E4F0";

const PAGE_W = 12240;
const MARGIN = 1080;
const CONTENT_W = PAGE_W - 2 * MARGIN;

// ── LOAD IMAGES ─────────────────────────────────────────────────────────
const ssoDir = "/sessions/hopeful-trusting-ritchie/mnt/SSO";
const headerLogo = fs.readFileSync(`${ssoDir}/image1.png`);
const coverLogo = fs.readFileSync(`${ssoDir}/image3.jpeg`);

// ── TABLE HELPERS (Hackett style) ───────────────────────────────────────
const tblBorder = { style: BorderStyle.SINGLE, size: 4, color: TABLE_BORDER };
const tblBorderOuter = { style: BorderStyle.SINGLE, size: 8, color: TABLE_BORDER };
const borders = { top: tblBorder, bottom: tblBorder, left: tblBorder, right: tblBorder };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function headerCell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: cellMargins,
    children: [new Paragraph({
      spacing: { before: 40, after: 40 },
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, italics: true, color: WHITE, font: "Calibri", size: 20 })],
    })],
  });
}

function cell(text, width, opts = {}) {
  const { bold, fill, color, fontSize, italics } = opts;
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined, margins: cellMargins,
    children: [new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: text || "", bold: !!bold, italics: !!italics, color: color || "333333", font: "Calibri", size: fontSize || 20 })],
    })],
  });
}

function riskCell(risk, width) {
  const map = {
    CRITICAL: { fill: RED_BG, color: RED_TEXT }, HIGH: { fill: ORANGE_BG, color: ORANGE_TEXT },
    MEDIUM: { fill: YELLOW_BG, color: YELLOW_TEXT }, LOW: { fill: BLUE_LIGHT, color: NAVY },
    OK: { fill: GREEN_BG, color: GREEN_TEXT },
  };
  const s = map[risk] || { fill: GRAY_BG, color: "333333" };
  return cell(risk, width, { bold: true, fill: s.fill, color: s.color });
}

function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: 300, after: 150 },
    children: [new TextRun({ text, font: level === HeadingLevel.HEADING_1 ? "Arial Narrow" : "Calibri" })],
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    alignment: AlignmentType.BOTH,
    children: [new TextRun({ text, font: "Garamond", size: 22, ...opts })],
  });
}

function boldPara(label, text) {
  return new Paragraph({
    spacing: { after: 100 },
    alignment: AlignmentType.BOTH,
    children: [
      new TextRun({ text: label, bold: true, font: "Garamond", size: 22 }),
      new TextRun({ text, font: "Garamond", size: 22 }),
    ],
  });
}

// ── Numbering configs ─────────────────────────────────────────────────
function makeNumberingConfigs() {
  const refs = ["steps1","steps2","steps3","steps4","steps5","bullets1","bullets2","bullets3","bullets4","bullets5"];
  return refs.map(ref => ({
    reference: ref,
    levels: [{
      level: 0,
      format: ref.startsWith("steps") ? LevelFormat.DECIMAL : LevelFormat.BULLET,
      text: ref.startsWith("steps") ? "%1." : "\u2022",
      alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } },
    }],
  }));
}

function numberedItem(ref, boldText, normalText) {
  return new Paragraph({
    spacing: { after: 80 },
    numbering: { reference: ref, level: 0 },
    children: [
      new TextRun({ text: boldText, bold: true, font: "Garamond", size: 22 }),
      new TextRun({ text: normalText, font: "Garamond", size: 22 }),
    ],
  });
}

// ── DATA (AI_Innovation_LAB only — account 754810878150) ───────────────

const adminUsers = [
  {
    user: "amohanty", mfa: "No", lastLogin: "Never", services: "0",
    keyStatus: "None", risk: "CRITICAL",
    usage: "This user has never logged into the console and has no access keys. The account was created on June 11, 2025 and has remained completely dormant for over 8 months. Despite being in the Administrators group, there is zero evidence of any activity whatsoever. Also listed in the SSO group Hackett_AIE_CloudInfra_Admins, but that SSO access has also never been used.",
    verdict: "REMOVE",
    detail: "Remove from the Administrators group immediately. Disable console password. If the user needs access in the future, re-provision with scoped permissions based on actual job function. Also remove from the SSO Admins group unless a specific future need is documented.",
  },
  {
    user: "ldelgado", mfa: "No", lastLogin: "5 days ago", services: "34",
    keyStatus: "None", risk: "HIGH",
    usage: "Actively uses the account across 34 AWS services: access-analyzer, account, autoscaling, billing, budgets, ce, cloudwatch, compute-optimizer, cost-optimization-hub, ec2, elasticloadbalancing, es (OpenSearch), freetier, guardduty, health, iam, kms, logs, notifications, organizations, outposts, payments, pricing, rds, resource-explorer-2, s3, servicecatalog, signin, ssm, sso, tax, uxc, and more. Last console sign-in was February 19, 2026. Listed as the POC for AI_Innovation_LAB and a member of the SSO CloudInfra Admins group.",
    verdict: "KEEP (with conditions)",
    detail: "Admin access is justified given the POC role and breadth of active usage across 34 services. However, the lack of MFA on an admin account with this level of access is a critical security gap. Action: enforce MFA within 48 hours. Consider whether a custom policy covering these 34 specific services could replace full AdministratorAccess.",
  },
  {
    user: "mfernandez", mfa: "Yes", lastLogin: "20 days ago", services: "48",
    keyStatus: "AKIA27...EWEYP7 (Active, 257 days old)", risk: "MEDIUM",
    usage: "The most active admin user in this account, accessing 48 services in the last 90 days: account, acm, application-autoscaling, applicationinsights, arc-zonal-shift, autoscaling, aws-marketplace, billing, budgets, ce, cloudwatch, cognito-identity, cognito-idp, compute-optimizer, cost-optimization-hub, ec2, eks, elasticache, elasticloadbalancing, es, freetier, guardduty, health, iam, kms, logs, notifications, oam, organizations, payments, pricing, ram, rds, resource-explorer-2, resource-groups, route53resolver, securityhub, servicecatalog, signin, ssm, sso, sts, support, tag, tax, uxc, and more. The access key was last used for EKS on Feb 4. MFA is enabled.",
    verdict: "KEEP",
    detail: "Admin access is clearly justified by the breadth and depth of usage (48 services). MFA is properly configured. The only action needed is to rotate the access key immediately \u2014 it is 257 days old, well past the 180-day best practice. After rotation, implement a 90-day rotation schedule.",
  },
  {
    user: "prodrigues", mfa: "No", lastLogin: "74 days ago", services: "25",
    keyStatus: "AKIA27...D2VXL (Active, 74 days old, last used 74d ago)", risk: "HIGH",
    usage: "Accessed 25 services in the 90-day window: account, aws-portal, billing, ce, cost-optimization-hub, ec2, eks, elasticache, es, freetier, health, iam, kms, notifications, organizations, rds, resource-explorer-2, secretsmanager, securityhub, servicecatalog, signin, sso, sts, support, uxc. The access key was used once for OpenSearch on December 12. Most recent Access Advisor activity was also December 13.",
    verdict: "CONDITIONAL KEEP",
    detail: "Usage pattern suggests periodic infrastructure work rather than daily admin tasks. The 74-day gap since last activity is concerning. Actions: (1) Enforce MFA immediately. (2) Deactivate the access key \u2014 it was only used once and likely for a one-off task. (3) Set a 30-day review: if no console activity resumes, downgrade to PowerUserAccess or a scoped custom policy.",
  },
  {
    user: "blemus", mfa: "Yes", lastLogin: "Today", services: "21",
    keyStatus: "AKIA27...F6X7VX (Active, created today)", risk: "OK",
    usage: "Newly provisioned user (created Feb 19) who has already accessed 21 services: access-analyzer, account, ce, cost-optimization-hub, ec2, ecs, freetier, health, iam, notifications, organizations, q, resource-explorer-2, s3, securityhub, servicecatalog, signin, sso, sts, support, uxc. MFA is properly enabled. Access key was created and used today for IAM.",
    verdict: "KEEP",
    detail: "Active and properly configured with MFA. The access key was just created today \u2014 confirm the intended purpose and whether it can be replaced with an IAM role for the specific use case. Monitor usage for the first 30 days to baseline the normal access pattern.",
  },
  {
    user: "cjardim", mfa: "No", lastLogin: "215 days ago", services: "0",
    keyStatus: "None", risk: "HIGH",
    usage: "Zero services accessed in the 90-day Access Advisor window. The last console login was July 24, 2025 \u2014 over 7 months ago. Has no access keys. The account has been completely dormant despite holding full admin privileges via the Administrators group.",
    verdict: "REMOVE",
    detail: "Remove from the Administrators group. Disable console password. If the user returns and needs access, create a new IAM user with scoped permissions based on the actual work required, or provision via SSO with an appropriate permission set.",
  },
  {
    user: "yamil.succar@thehackettgroup.com", mfa: "Yes", lastLogin: "8 days ago", services: "23",
    keyStatus: "None", risk: "LOW",
    usage: "Accessed 23 services, primarily billing and governance-related: access-analyzer, account, billing, budgets, ce, compute-optimizer, cost-optimization-hub, ec2, freetier, health, iam, notifications, organizations, payments, q, securityhub, servicecatalog, signin, sso, support, tax, uxc. Notably, this user has AdministratorAccess attached directly to the user (not via the Administrators group), which is a governance concern \u2014 direct policy attachments are harder to audit and manage at scale.",
    verdict: "RESTRUCTURE",
    detail: "The actual usage is billing, cost management, security posture, and IAM review \u2014 none of which requires full admin. Actions: (1) Remove the directly-attached AdministratorAccess policy. (2) Create a custom policy scoped to the 23 services actually used, OR assign to the Administrators group if full admin is truly needed. (3) For the billing/cost use case, consider a dedicated Billing_Viewer permission set via SSO instead.",
  },
];

const unusedKeysData = [
  { user: "azuredevops.LAB.aixplr.draft", keyId: "AKIA27...33R2", age: "239d", lastUsed: "239d ago (STS)", risk: "MEDIUM", action: "Deactivate immediately \u2014 pipeline has been inactive for 8 months with zero service activity in the 90-day window" },
  { user: "mfernandez", keyId: "AKIA27...EKEWEYP7", age: "257d", lastUsed: "20d ago (EKS)", risk: "MEDIUM", action: "Rotate immediately \u2014 key is 257 days old (limit: 180d) but actively used for EKS" },
  { user: "prodrigues", keyId: "AKIA27...FS3D2VXL", age: "74d", lastUsed: "74d ago (OpenSearch)", risk: "HIGH", action: "Deactivate \u2014 used only once on Dec 12, appears to be a one-off task. No MFA on admin account compounds risk" },
  { user: "blemus", keyId: "AKIA27...DDDNF6X7VX", age: "0d", lastUsed: "Today (IAM)", risk: "LOW", action: "Confirm purpose \u2014 key was just created. Evaluate whether an IAM role can replace it" },
  { user: "tsgam-use1-s3proxy-north-lab", keyId: "AKIA27...MHRVVPZK", age: "92d", lastUsed: "47d ago (S3)", risk: "OK", action: "Plan migration to Instance Profile / Task Role. Key is approaching 90-day rotation threshold" },
  { user: "azuredevops.LAB.north.lab", keyId: "AKIA27...F4CDKSH5", age: "100d", lastUsed: "47d ago (IAM)", risk: "LOW", action: "Plan OIDC migration \u2014 key is actively used for Terraform deployments across 14 services" },
];

const dormantAccounts = [
  { user: "amohanty", lastActivity: "Never", created: "2025-06-11", risk: "CRITICAL", action: "Disable console, remove from Administrators group \u2014 8+ months dormant with admin privileges" },
  { user: "tests", lastActivity: "Never", created: "2026-02-24 (today)", risk: "CRITICAL", action: "Investigate who created this account. No group membership, only IAMUserChangePassword. Delete if unauthorized" },
  { user: "cjardim", lastActivity: "215 days ago", created: "2025-06-30", risk: "HIGH", action: "Disable console, remove from Administrators \u2014 7+ months dormant, zero services in 90-day window" },
];

const serviceAccounts = [
  {
    user: "azuredevops.AI-Innovation-LAB.aixplr.draft",
    purpose: "AzureDevOps Terraform pipeline for the aixplr draft environment",
    keyAge: "239 days", lastUsed: "239 days ago (STS)", servicesUsed: "0 in 90-day window",
    risk: "MEDIUM \u2014 stale pipeline, potential orphaned credential",
    alternative: "Deactivate key now. If pipeline is still needed, migrate to OIDC Federation.",
    detail: "This key has not been used in 8 months and the pipeline shows zero service activity in the Access Advisor window. The credential is likely orphaned. Deactivate the key immediately. If the aixplr draft pipeline needs to be revived, implement OIDC federation before creating a new credential.",
  },
  {
    user: "azuredevops.AI-Innovation-LAB.north.lab",
    purpose: "AzureDevOps Terraform pipeline for the north lab environment",
    keyAge: "100 days", lastUsed: "47 days ago (IAM)", servicesUsed: "14 services: dynamodb, ec2, eks, elasticache, elasticloadbalancing, es, iam, kms, logs, rds, resource-groups, s3, secretsmanager, sts",
    risk: "LOW \u2014 actively used, properly scoped policy",
    alternative: "OIDC Federation with Azure DevOps (highest-priority migration candidate)",
    detail: "This is the most actively used service account, deploying infrastructure across 14 services via Terraform. The existing policy (AI-Innovation-LAB-north-lab-terraform-policy) is already properly scoped. Migrate to OIDC to eliminate the long-lived key while keeping the same permission policy attached to the new IAM Role.",
  },
  {
    user: "tsgam-use1-s3proxy-north-lab-8z6lcm",
    purpose: "TSGAM infrastructure \u2014 S3 proxy service for the north lab environment",
    keyAge: "92 days", lastUsed: "47 days ago (S3)", servicesUsed: "1 service: s3",
    risk: "OK \u2014 well-scoped, single-service access",
    alternative: "EC2 Instance Profile or ECS Task Role",
    detail: "This service account only accesses S3 and has a properly scoped policy (tsgam-use1-s3proxy-north-lab-policy). Replace the access key with an IAM Role attached as an Instance Profile (EC2), Task Role (ECS), or IRSA (EKS) depending on where the S3 proxy runs. The AWS SDK will automatically use the role credentials from the instance metadata service.",
  },
];

// ── BUILD DOCUMENT (Hackett Group Template Style) ──────────────────────

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Garamond", size: 22 },
        paragraph: { spacing: { before: 240, line: 280 }, alignment: AlignmentType.BOTH },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial Narrow", color: NAVY, allCaps: true, characterSpacing: 20 },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0, pageBreakBefore: true },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: TEXT2 },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: NAVY, allCaps: true, characterSpacing: 20 },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: { config: makeNumberingConfigs() },
  sections: [
    // ══════════════════════════════════════════════════════════════════
    // COVER PAGE (separate section — no header/footer)
    // ══════════════════════════════════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: 15840 },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      children: [
        // Large Hackett Group Logo (centered)
        new Paragraph({
          alignment: AlignmentType.LEFT,
          spacing: { before: 600, after: 400 },
          children: [
            new ImageRun({
              type: "jpg",
              data: coverLogo,
              transformation: { width: 468, height: 86 },
              altText: { title: "The Hackett Group", description: "Hackett Group Logo", name: "HackettLogo" },
            }),
          ],
        }),

        // Thick navy blue horizontal line
        new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 48, color: NAVY, space: 1 } },
          spacing: { after: 600 },
          children: [],
        }),

        // Project Title
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [
            new TextRun({ text: "IAM Security Audit", font: "Calibri", size: 52, bold: true, color: NAVY }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [
            new TextRun({ text: "AI_Innovation_LAB", font: "Calibri", size: 40, color: TEXT2 }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [
            new TextRun({ text: "Consolidated Action Plan", font: "Calibri", size: 30, color: TEXT2 }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [
            new TextRun({ text: "Account 754810878150  |  11 IAM Users  |  6 Access Keys  |  3 Service Accounts", font: "Calibri", size: 22, color: "666666" }),
          ],
        }),

        // Spacers
        new Paragraph({ spacing: { before: 800 } }),
        new Paragraph({ spacing: { before: 200 } }),
        new Paragraph({ spacing: { before: 200 } }),
        new Paragraph({ spacing: { before: 200 } }),
        new Paragraph({ spacing: { before: 200 } }),
        new Paragraph({ spacing: { before: 200 } }),

        // Prepared by
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: "Prepared by", font: "Calibri", size: 24, color: "666666" })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: "The Hackett Group", font: "Calibri", size: 24, bold: true, color: NAVY })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "Date: February 2026", font: "Calibri", size: 24, color: "666666" })],
        }),
      ],
    },

    // ══════════════════════════════════════════════════════════════════
    // BODY SECTION (with header & footer)
    // ══════════════════════════════════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: 15840 },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              spacing: { before: 0, after: 0 },
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              children: [
                new TextRun({ text: "IAM Security Audit \u2014 AI_Innovation_LAB", font: "Arial Narrow", size: 20, bold: true, color: NAVY }),
                new TextRun({ text: "\t" }),
                new ImageRun({
                  type: "png",
                  data: headerLogo,
                  transformation: { width: 132, height: 21 },
                  altText: { title: "Hackett Group", description: "Hackett Group Logo Small", name: "HackettSmall" },
                }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              children: [
                new TextRun({ text: "\u00A9 2026 The Hackett Group, Inc. All rights reserved.", font: "Calibri", size: 16, color: "666666" }),
                new TextRun({ text: "\t" }),
                new TextRun({ text: "Page ", font: "Calibri", size: 16, color: "666666" }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 16, color: "666666" }),
              ],
            }),
          ],
        }),
      },
      children: [
        // ── SCOPE BOX ──────────────────────────────────────────────────
        new Paragraph({
          spacing: { before: 200, after: 200 },
          children: [new TextRun({ text: "Scope", bold: true, font: "Arial Narrow", size: 28, color: NAVY })],
        }),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
          rows: [new TableRow({ children: [
            new TableCell({
              borders: {
                top: { style: BorderStyle.SINGLE, size: 2, color: NAVY },
                bottom: { style: BorderStyle.SINGLE, size: 2, color: NAVY },
                left: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
                right: { style: BorderStyle.SINGLE, size: 2, color: NAVY },
              },
              width: { size: CONTENT_W, type: WidthType.DXA },
              shading: { fill: "E8EEF4", type: ShadingType.CLEAR },
              margins: { top: 200, bottom: 200, left: 300, right: 300 },
              children: [
                para("This plan covers four areas for the AI_Innovation_LAB AWS account (754810878150):"),
                numberedItem("steps1", "Unused Access Keys & Dormant Accounts ", "\u2014 deactivate stale credentials and disable inactive users."),
                numberedItem("steps1", "Administrator Access Assessment ", "\u2014 per-user evaluation of admin necessity based on actual 90-day service usage."),
                numberedItem("steps1", "Service Account Modernization ", "\u2014 replace long-lived access keys with OIDC federation and IAM roles."),
                numberedItem("steps1", "SSO Consolidation ", "\u2014 proposed group structure for unified SSO access to this account."),
              ],
            }),
          ]})]
        }),

        new Paragraph({ spacing: { before: 300 } }),
        boldPara("Account: ", "AI_Innovation_LAB (754810878150)"),
        boldPara("POC: ", "Leonardo Delgado (ldelgado)"),
        boldPara("Audit Date: ", "February 24, 2026"),
        boldPara("Data Source: ", "iam_user_audit.py with Access Advisor (90-day window)"),

        // ── Risk Summary ───────────────────────────────────────────────
        new Paragraph({ spacing: { before: 300 } }),
        new Paragraph({
          spacing: { before: 200, after: 150 },
          children: [new TextRun({ text: "Risk Summary", bold: true, font: "Arial Narrow", size: 28, color: NAVY })],
        }),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [1500, 8580],
          rows: [
            new TableRow({ children: [headerCell("Risk", 1500), headerCell("Users", 8580)] }),
            new TableRow({ children: [riskCell("CRITICAL", 1500), cell("amohanty (admin, never used), tests (no permissions, created today)", 8580)] }),
            new TableRow({ children: [riskCell("HIGH", 1500), cell("cjardim (dormant 7mo, no MFA), ldelgado (active but no MFA), prodrigues (no MFA, key stale)", 8580)] }),
            new TableRow({ children: [riskCell("MEDIUM", 1500), cell("mfernandez (key 257d old), azuredevops.aixplr.draft (key stale 8mo)", 8580)] }),
            new TableRow({ children: [riskCell("LOW", 1500), cell("azuredevops.north.lab (direct policy), yamil.succar (direct admin policy, not via group)", 8580)] }),
            new TableRow({ children: [riskCell("OK", 1500), cell("blemus (MFA, active, 21 services), tsgam-s3proxy (well-scoped, S3 only)", 8580)] }),
          ],
        }),

        new Paragraph({ children: [new PageBreak()] }),

        // ══════════════════════════════════════════════════════════════
        // SECTION 1: UNUSED KEYS & DORMANT ACCOUNTS
        // ══════════════════════════════════════════════════════════════
        heading("1. Unused Access Keys & Dormant Accounts", HeadingLevel.HEADING_1),
        para("All six active access keys and three dormant accounts in AI_Innovation_LAB, with risk level and recommended action."),

        heading("1.1 Access Keys Requiring Action", HeadingLevel.HEADING_2),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [2200, 1400, 700, 1100, 700, 3980],
          rows: [
            new TableRow({ children: [
              headerCell("User", 2200), headerCell("Key ID", 1400), headerCell("Age", 700),
              headerCell("Last Used", 1100), headerCell("Risk", 700), headerCell("Action", 3980),
            ]}),
            ...unusedKeysData.map(r => new TableRow({ children: [
              cell(r.user, 2200, { bold: true, fontSize: 18 }), cell(r.keyId, 1400, { fontSize: 18 }),
              cell(r.age, 700, { fontSize: 18 }), cell(r.lastUsed, 1100, { fontSize: 18 }),
              riskCell(r.risk, 700), cell(r.action, 3980, { fontSize: 18 }),
            ]})),
          ],
        }),

        new Paragraph({ spacing: { before: 300 } }),
        heading("1.2 Dormant / Suspicious Accounts", HeadingLevel.HEADING_2),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [1800, 1200, 1200, 800, 5080],
          rows: [
            new TableRow({ children: [
              headerCell("User", 1800), headerCell("Last Activity", 1200), headerCell("Created", 1200),
              headerCell("Risk", 800), headerCell("Action", 5080),
            ]}),
            ...dormantAccounts.map(r => new TableRow({ children: [
              cell(r.user, 1800, { bold: true, fontSize: 18 }), cell(r.lastActivity, 1200, { fontSize: 18 }),
              cell(r.created, 1200, { fontSize: 18 }), riskCell(r.risk, 800), cell(r.action, 5080, { fontSize: 18 }),
            ]})),
          ],
        }),

        new Paragraph({ children: [new PageBreak()] }),

        // ══════════════════════════════════════════════════════════════
        // SECTION 2: ADMINISTRATOR ACCESS ASSESSMENT
        // ══════════════════════════════════════════════════════════════
        heading("2. Administrator Access Assessment", HeadingLevel.HEADING_1),
        para("Seven users in AI_Innovation_LAB hold AdministratorAccess. Each is assessed below based on their actual 90-day service usage from IAM Access Advisor, console login history, MFA status, and role within the organization."),

        ...adminUsers.flatMap(u => {
          const verdictColor = u.verdict.startsWith("REMOVE") ? RED_TEXT : u.verdict.startsWith("KEEP") ? GREEN_TEXT : u.verdict.startsWith("CONDITIONAL") ? ORANGE_TEXT : YELLOW_TEXT;
          const verdictFill = u.verdict.startsWith("REMOVE") ? RED_BG : u.verdict.startsWith("KEEP") ? GREEN_BG : u.verdict.startsWith("CONDITIONAL") ? ORANGE_BG : YELLOW_BG;
          return [
            // User header bar
            new Table({
              width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
              rows: [new TableRow({ children: [new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 4, color: NAVY },
                  bottom: tblBorder, left: tblBorder, right: tblBorder,
                },
                width: { size: CONTENT_W, type: WidthType.DXA },
                shading: { fill: GRAY_BG, type: ShadingType.CLEAR },
                margins: { top: 80, bottom: 80, left: 200, right: 200 },
                children: [new Paragraph({ children: [
                  new TextRun({ text: u.user, bold: true, font: "Arial Narrow", size: 26, color: NAVY }),
                ]})],
              })]})],
            }),
            // Stats row
            new Table({
              width: { size: CONTENT_W, type: WidthType.DXA },
              columnWidths: [1680, 2016, 1680, 2016, 2688],
              rows: [
                new TableRow({ children: [
                  headerCell("MFA", 1680), headerCell("Last Login", 2016), headerCell("Services (90d)", 1680),
                  headerCell("Access Keys", 2016), headerCell("Verdict", 2688),
                ]}),
                new TableRow({ children: [
                  cell(u.mfa, 1680, { bold: true, color: u.mfa === "Yes" ? GREEN_TEXT : RED_TEXT }),
                  cell(u.lastLogin, 2016), cell(u.services, 1680, { bold: true }),
                  cell(u.keyStatus, 2016, { fontSize: 18 }),
                  cell(u.verdict, 2688, { bold: true, fill: verdictFill, color: verdictColor, fontSize: 18 }),
                ]}),
              ],
            }),
            new Paragraph({
              spacing: { before: 100, after: 40 },
              children: [new TextRun({ text: "Usage Analysis:", bold: true, font: "Calibri", size: 20, color: NAVY })],
            }),
            new Paragraph({
              spacing: { after: 240 },
              alignment: AlignmentType.BOTH,
              children: [new TextRun({ text: u.usage, font: "Garamond", size: 20, color: "444444" })],
            }),
          ];
        }),

        new Paragraph({ children: [new PageBreak()] }),

        // ══════════════════════════════════════════════════════════════
        // SECTION 3: SERVICE ACCOUNT MODERNIZATION
        // ══════════════════════════════════════════════════════════════
        heading("3. Service Account Modernization", HeadingLevel.HEADING_1),
        para("AI_Innovation_LAB has three non-human service accounts, all using long-lived access keys. Below is the migration path for each to eliminate key-based authentication."),

        ...serviceAccounts.flatMap(s => [
          new Table({
            width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
            rows: [new TableRow({ children: [new TableCell({
              borders: {
                top: { style: BorderStyle.SINGLE, size: 4, color: NAVY },
                bottom: tblBorder, left: tblBorder, right: tblBorder,
              },
              width: { size: CONTENT_W, type: WidthType.DXA },
              shading: { fill: GRAY_BG, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 200, right: 200 },
              children: [new Paragraph({ children: [new TextRun({ text: s.user, bold: true, font: "Arial Narrow", size: 22, color: NAVY })] })],
            })]})],
          }),
          boldPara("Purpose: ", s.purpose),
          boldPara("Current Key: ", `${s.keyAge} old, last used ${s.lastUsed}`),
          boldPara("Services Used (90d): ", s.servicesUsed),
          boldPara("Risk: ", s.risk),
          new Paragraph({
            spacing: { before: 80, after: 40 },
            children: [
              new TextRun({ text: "Recommended Alternative: ", bold: true, font: "Garamond", size: 22 }),
              new TextRun({ text: s.alternative, bold: true, font: "Garamond", size: 22, color: GREEN_TEXT }),
            ],
          }),
          new Paragraph({
            spacing: { after: 240 },
            alignment: AlignmentType.BOTH,
            children: [new TextRun({ text: s.detail, font: "Garamond", size: 20, color: "444444" })],
          }),
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ══════════════════════════════════════════════════════════════
        // SECTION 4: SSO CONSOLIDATION
        // ══════════════════════════════════════════════════════════════
        heading("4. SSO Consolidation for AI_Innovation_LAB", HeadingLevel.HEADING_1),

        // ── Existing SSO Roles Reference ──────────────────────────────
        // From: Copy of ai_analytics_access.xlsx
        //   AIE_AnalyticsLab_Admin_Role        → AdministratorAccess
        //   AIE_AnalyticsLab_DataEngineer       → Data pipeline policies (AppFlow, DocDB, ECR, ECS, RDS, Batch, StepFunctions, Glue, Athena, etc.)
        //   AIE_AnalyticsLab_AIEngineer_Role    → AI/ML policies (Bedrock, DynamoDB, ECS, Route53, S3, CloudWatch)
        //   AIE_AnalyticsLab_Developer_Role     → Developer policies (ECR, ECS, RDS read, S3 read, Secrets, CloudWatch, Copilot)
        //
        // Proposed NEW roles (do not exist yet):
        //   AIE_AnalyticsLab_InfraSupport_Role  → For prodrigues: infra read/write on EC2, EKS, ElastiCache, OpenSearch, RDS, IAM, KMS, SecretsManager, SecurityHub, Billing, CostExplorer
        //   AIE_AnalyticsLab_BillingGovernance_Role → For yamil.succar: Billing, Budgets, CostExplorer, SecurityHub, IAM read, Organizations, Payments, Tax

        heading("4.1 Existing SSO Roles", HeadingLevel.HEADING_2),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [3400, 6680],
          rows: [
            new TableRow({ children: [
              headerCell("SSO Role Name", 3400), headerCell("Permission Set / Scope", 6680),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_Admin_Role", 3400, { bold: true }),
              cell("AdministratorAccess (full admin to all AWS services)", 6680, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_DataEngineer", 3400, { bold: true }),
              cell("Data pipeline: AppFlow, DocDB, ECR, ECS, RDS, Batch, StepFunctions, Glue, Athena, LakeFormation, Redshift, DynamoDB, EventBridge, S3, Lambda, SecretsManager, SSM, KMS", 6680, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_AIEngineer_Role", 3400, { bold: true }),
              cell("AI/ML: Bedrock, DynamoDB, ECS, Route53, S3 read, CloudWatch, SQS, RDS, SSM Parameter Store", 6680, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_Developer_Role", 3400, { bold: true }),
              cell("Developer: ECR, ECS, RDS read, S3 read, CloudWatch read, SecretsManager, Copilot, CloudFormation read, Bedrock invoke", 6680, { fontSize: 18 }),
            ]}),
          ],
        }),

        new Paragraph({ spacing: { before: 300 } }),
        heading("4.2 Proposed New Roles", HeadingLevel.HEADING_2),
        para("The following roles do not exist in the current SSO configuration and need to be created to support least-privilege access for users being downgraded from AdministratorAccess."),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [3400, 6680],
          rows: [
            new TableRow({ children: [
              headerCell("Proposed SSO Role Name", 3400), headerCell("Permission Set Policies", 6680),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_InfraSupport_Role", 3400, { bold: true, color: NAVY }),
              cell("AWS Managed: ViewOnlyAccess, SecurityAudit, AmazonEC2ReadOnlyAccess, AmazonEKSClusterPolicy, AmazonRDSReadOnlyAccess, CloudWatchReadOnlyAccess. Inline: EC2/EKS/ElastiCache/OpenSearch limited write, IAM read, KMS decrypt, SecretsManager read, SecurityHub read, Billing/CostExplorer/CostOptimizationHub read, SSM read.", 6680, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_BillingGovernance_Role", 3400, { bold: true, color: NAVY }),
              cell("AWS Managed: Billing, AWSBudgetsActionsWithAWSResourceControlAccess, SecurityAudit, ViewOnlyAccess, IAMReadOnlyAccess. Inline: CostExplorer, CostOptimizationHub, ComputeOptimizer, Organizations read, Payments read, Tax read, SecurityHub read, IAM AccessAnalyzer read, FreeTier read.", 6680, { fontSize: 18 }),
            ]}),
          ],
        }),

        new Paragraph({ spacing: { before: 300 } }),
        heading("4.3 Proposed User Assignments", HeadingLevel.HEADING_2),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [2800, 2800, 4480],
          rows: [
            new TableRow({ children: [
              headerCell("SSO Role", 2800),
              headerCell("Proposed Members", 2800), headerCell("Rationale", 4480),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_Admin_Role", 2800, { bold: true }),
              cell("ldelgado, mfernandez, blemus", 2800),
              cell("Active admins with confirmed usage across 34, 48, and 21 services respectively. Existing role covers their needs. Remove amohanty (dormant).", 4480, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_InfraSupport_Role", 2800, { bold: true, color: NAVY }),
              cell("prodrigues", 2800),
              cell("25 services, mostly infra: EC2, EKS, ElastiCache, OpenSearch, RDS, IAM, KMS, SecretsManager, SecurityHub, Billing. Periodic usage pattern does not justify full admin. New role scoped to actual services.", 4480, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("AIE_AnalyticsLab_BillingGovernance_Role", 2800, { bold: true, color: NAVY }),
              cell("yamil.succar", 2800),
              cell("23 services focused on billing, cost management, security posture, and IAM review. None require full admin. New role scoped to governance and financial operations.", 4480, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("None (Inactive)", 2800, { fill: RED_BG, color: RED_TEXT }),
              cell("amohanty, cjardim", 2800),
              cell("Dormant users. amohanty: never logged in (8+ months). cjardim: last login 215 days ago, zero services in 90-day window. Parked until reactivation is requested with justification.", 4480, { fontSize: 18 }),
            ]}),
          ],
        }),

        new Paragraph({ spacing: { before: 300 } }),
        heading("4.4 Changes Summary", HeadingLevel.HEADING_2),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [2000, 2600, 2600, 2880],
          rows: [
            new TableRow({ children: [
              headerCell("User", 2000), headerCell("Current Access", 2600),
              headerCell("Proposed SSO Role", 2600), headerCell("Change", 2880),
            ]}),
            new TableRow({ children: [
              cell("ldelgado", 2000, { bold: true }),
              cell("IAM Administrators group + SSO Hackett_AIE_CloudInfra_Admins", 2600, { fontSize: 18 }),
              cell("AIE_AnalyticsLab_Admin_Role", 2600, { bold: true }),
              cell("No permission change. Migrate to new SSO role. Disable IAM console password after SSO confirmed.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("mfernandez", 2000, { bold: true }),
              cell("IAM Administrators group", 2600),
              cell("AIE_AnalyticsLab_Admin_Role", 2600, { bold: true }),
              cell("Add to SSO Admin role. Disable IAM console password after SSO confirmed.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("blemus", 2000, { bold: true }),
              cell("IAM Administrators group", 2600),
              cell("AIE_AnalyticsLab_Admin_Role", 2600, { bold: true }),
              cell("Add to SSO Admin role. Disable IAM console password after SSO confirmed.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("prodrigues", 2000, { bold: true }),
              cell("IAM Administrators group", 2600),
              cell("AIE_AnalyticsLab_InfraSupport_Role", 2600, { bold: true, fill: YELLOW_BG, color: NAVY }),
              cell("Downgrade from admin. Create new SSO role scoped to infra + security services. Disable IAM console password.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("yamil.succar", 2000, { bold: true }),
              cell("Direct AdministratorAccess policy (not via group)", 2600, { fontSize: 18 }),
              cell("AIE_AnalyticsLab_BillingGovernance_Role", 2600, { bold: true, fill: YELLOW_BG, color: NAVY }),
              cell("Remove direct IAM policy. Create new SSO role scoped to billing/governance. Disable IAM console password.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("amohanty", 2000, { bold: true }),
              cell("IAM Administrators + SSO Hackett_AIE_CloudInfra_Admins", 2600, { fontSize: 18 }),
              cell("None (Inactive)", 2600, { fill: RED_BG, color: RED_TEXT }),
              cell("Remove from all active groups and roles. Disable IAM console. Park until reactivation requested.", 2880, { fontSize: 18 }),
            ]}),
            new TableRow({ children: [
              cell("cjardim", 2000, { bold: true }),
              cell("IAM Administrators group", 2600),
              cell("None (Inactive)", 2600, { fill: RED_BG, color: RED_TEXT }),
              cell("Remove from Administrators. Disable IAM console. Park until reactivation requested.", 2880, { fontSize: 18 }),
            ]}),
          ],
        }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/hopeful-trusting-ritchie/mnt/SSO/IAM_Audit_Action_Plan.docx", buffer);
  console.log("Document created:", buffer.length, "bytes");
});
