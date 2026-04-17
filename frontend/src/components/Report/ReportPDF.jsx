import React from "react";
import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";

const GOLD = "#b8860b";

const s = StyleSheet.create({
  page: { padding: "32px 40px", fontFamily: "Helvetica", backgroundColor: "#fff", fontSize: 11, color: "#111827" },
  h1: { fontSize: 22, fontWeight: "bold", marginBottom: 3 },
  scoreLine: { fontSize: 12, color: "#6b7280", marginBottom: 18 },
  scoreNum: { fontSize: 26, fontWeight: "bold", color: GOLD },
  section: { marginBottom: 14 },
  h2: { fontSize: 13, fontWeight: "bold", color: GOLD, borderBottomWidth: 1, borderBottomColor: "#e5e7eb", paddingBottom: 3, marginBottom: 7 },
  body: { fontSize: 11, lineHeight: 1.55, color: "#374151" },
  li: { fontSize: 11, lineHeight: 1.6, marginBottom: 3, color: "#374151" },
  bold: { fontWeight: "bold" },
  roleBlock: { marginBottom: 10 },
  roleTitle: { fontSize: 12, fontWeight: "bold", marginBottom: 2 },
  roleMeta: { fontSize: 10, color: "#6b7280", marginBottom: 4 },
  companies: { fontSize: 10, color: "#6b7280", marginTop: 3 },
  reviewLabel: { fontSize: 11, fontWeight: "bold", color: "#1c1917", marginBottom: 2 },
  reviewText: { fontSize: 11, color: "#374151", marginBottom: 8, lineHeight: 1.5 },
});

export function ReportPDF({ result }) {
  const {
    resumeScore = 0, summary, resumeSectionsReview = {}, criticalImprovements = [],
    topRoles = [], jobSearchStrategies = [], skillsToHighlight = [],
    skillsToDevelop = [], keyAchievements = [],
  } = result;

  return (
    <Document>
      <Page size="A4" style={s.page}>

        {/* Header */}
        <View style={{ marginBottom: 16 }}>
          <Text style={s.h1}>Resume Analysis Report</Text>
          <Text style={s.scoreLine}>
            Score: <Text style={s.scoreNum}>{resumeScore}</Text> / 100
          </Text>
        </View>

        {summary && (
          <View style={s.section}>
            <Text style={s.h2}>Profile Summary</Text>
            <Text style={s.body}>{summary}</Text>
          </View>
        )}

        {keyAchievements.length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Key Achievements</Text>
            {keyAchievements.map((a, i) => <Text key={i} style={s.li}>• {a}</Text>)}
          </View>
        )}

        {criticalImprovements.length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Critical Improvements</Text>
            {criticalImprovements.map((c, i) => <Text key={i} style={s.li}>{i + 1}. {c}</Text>)}
          </View>
        )}

        {(skillsToHighlight.length > 0 || skillsToDevelop.length > 0) && (
          <View style={s.section}>
            <Text style={s.h2}>Skills</Text>
            {skillsToHighlight.length > 0 && (
              <Text style={s.body}>
                <Text style={s.bold}>You excel at: </Text>{skillsToHighlight.join(" · ")}
              </Text>
            )}
            {skillsToDevelop.length > 0 && (
              <Text style={{ ...s.body, marginTop: 4 }}>
                <Text style={s.bold}>Consider developing: </Text>{skillsToDevelop.join(" · ")}
              </Text>
            )}
          </View>
        )}

        {Object.keys(resumeSectionsReview).length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Resume Section Review</Text>
            {[
              ["professional_summary", "Professional Summary"],
              ["work_experience", "Work Experience"],
              ["skills_section", "Skills"],
              ["education", "Education"],
              ["overall_presentation", "Overall Presentation"],
            ].map(([key, label]) => resumeSectionsReview[key] ? (
              <View key={key}>
                <Text style={s.reviewLabel}>{label}</Text>
                <Text style={s.reviewText}>{resumeSectionsReview[key]}</Text>
              </View>
            ) : null)}
          </View>
        )}

        {topRoles.length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Top Matching Roles</Text>
            {topRoles.map((role, i) => (
              <View key={i} style={s.roleBlock} wrap={false}>
                <Text style={s.roleTitle}>{role.title} — {role.match_percentage}% match</Text>
                <Text style={s.roleMeta}>{role.reason}</Text>
                {(role.resume_gaps || []).map((g, k) => <Text key={k} style={s.li}>• Gap: {g}</Text>)}
                {(role.application_tips || []).map((t, k) => <Text key={k} style={s.li}>• Tip: {t}</Text>)}
                {(role.target_companies || []).length > 0 && (
                  <Text style={s.companies}>Target companies: {role.target_companies.join(", ")}</Text>
                )}
              </View>
            ))}
          </View>
        )}

        {jobSearchStrategies.length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Job Search Strategies</Text>
            {jobSearchStrategies.map((j, i) => <Text key={i} style={s.li}>{i + 1}. {j}</Text>)}
          </View>
        )}

      </Page>
    </Document>
  );
}
