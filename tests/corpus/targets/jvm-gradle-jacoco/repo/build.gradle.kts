plugins { jacoco }
jacocoTestCoverageVerification {
  violationRules { rule { limit { minimum = "0.80".toBigDecimal() } } }
}
