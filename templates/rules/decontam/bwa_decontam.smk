# =============================================================================
# Rule template: BWA-MEM2 host/contaminant decontamination
# Maps reads to one or more reference genomes sequentially; retains only
# read pairs where BOTH mates are unmapped (-f 12) and not secondary (-F 256).
#
# If multiple decontam_refs are listed, rules are chained: the unmapped output
# of ref[n] becomes the input of ref[n+1]. bfx-dag generates one rule per ref.
# =============================================================================

rule bwa_decontam_<<ref_name>>:
    input:
        r1 = <<input_r1>>,
        r2 = <<input_r2>>,
    output:
        r1        = os.path.join(config["outdir"], "decontam", "{sample}_R1_no_<<ref_name>>.fastq.gz"),
        r2        = os.path.join(config["outdir"], "decontam", "{sample}_R2_no_<<ref_name>>.fastq.gz"),
        singleton = os.path.join(config["outdir"], "decontam", "{sample}_singleton_no_<<ref_name>>.fastq.gz"),
        flagstat  = os.path.join(config["outdir"], "decontam", "{sample}_<<ref_name>>.flagstat"),
    log:
        os.path.join(config["logdir"], "decontam", "{sample}_bwa_<<ref_name>>.log"),
    threads: <<threads>>
    resources:
        mem_mb  = <<mem_mb>>,
        runtime = <<runtime_min>>,
    conda:
        "<<conda_env>>"
    params:
        reference = "<<bwa_index_path>>",
        extra_bwa = <<extra_bwa>>,
    shell:
        """
        (bwa-mem2 mem \
            -t {threads} \
            {params.extra_bwa} \
            {params.reference} \
            {input.r1} {input.r2} \
        | samtools view -bS - \
        | tee >(samtools flagstat - > {output.flagstat}) \
        | samtools sort -n -m 2G -@ 4 - \
        | samtools fastq \
            -f 12 -F 256 \
            -1 {output.r1} \
            -2 {output.r2} \
            -s {output.singleton} \
            -) 2> {log}
        """
