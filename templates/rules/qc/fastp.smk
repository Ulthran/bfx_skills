# =============================================================================
# Rule template: fastp QC
# Generated into project workflow/Snakefile by bfx-dag
# Variables in <<double_brackets>> are replaced at DAG build time.
# =============================================================================

rule fastp_qc:
    input:
        r1 = lambda wc: samples.loc[wc.sample, "R1"],
        r2 = lambda wc: samples.loc[wc.sample, "R2"],
    output:
        r1  = os.path.join(config["outdir"], "qc", "{sample}_R1_qc.fastq.gz"),
        r2  = os.path.join(config["outdir"], "qc", "{sample}_R2_qc.fastq.gz"),
        json = os.path.join(config["outdir"], "qc", "{sample}_fastp.json"),
        html = os.path.join(config["outdir"], "qc", "{sample}_fastp.html"),
    log:
        os.path.join(config["logdir"], "qc", "{sample}_fastp.log"),
    threads: <<threads>>
    resources:
        mem_mb   = <<mem_mb>>,
        runtime  = <<runtime_min>>,
    conda:
        "<<conda_env>>"
    params:
        min_length           = <<min_length>>,
        complexity_threshold = <<complexity_threshold>>,
        extra                = <<extra>>,
    shell:
        """
        fastp \
            --in1 {input.r1} --out1 {output.r1} \
            --in2 {input.r2} --out2 {output.r2} \
            --json {output.json} --html {output.html} \
            --thread {threads} \
            --length_required {params.min_length} \
            --low_complexity_filter \
            --complexity_threshold {params.complexity_threshold} \
            --detect_adapter_for_pe \
            {params.extra} \
            2> {log}
        """
