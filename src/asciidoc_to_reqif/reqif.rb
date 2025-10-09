class ReqIfConverter
    include Asciidoctor::Converter
    register_for 'plainxml'

    def initialize *args
        super
        outfilesuffix '.xml'
        @references = Hash.new()
    end

    def is_requirement node
        node.node_name == 'sidebar' and node.attributes.key?(1) and node.attributes[1] == 'requirement'
    end

    def is_note node
        node.node_name == 'admonition' and node.attributes.key?('name') and node.attributes['name'] == 'note'
    end

    def convert_document node
        a = node.attributes
        <<~EOS.chomp
        <document xmlns:xhtml="http://www.w3.org/1999/xhtml"
         name="#{a['docname']}"
         srcdir="#{a['docdir']}"
         title="#{a['doctitle']}"
         imagesdir="#{a['imagesdir']}"
         >
        #{node.content}
        </document>
        EOS
    end

    def convert_requirement node
        a = node.attributes
        <<~EOS.chomp
        <requirement
            id="#{a['id']}"
            title="#{a['title']}"
            keyword="#{a['keyword']}"
            category="#{a['category']}"
            role="#{a.key?('sdc_role') ? a['sdc_role'] : ''}"
            >
        <!-- #{a} -->
        #{node.content}
        </requirement>
        EOS
    end

    def convert_paragraph node
        if true#self.is_requirement node.parent or self.is_note node.parent
            <<~EOS.chomp
            <xhtml:p>#{node.content}</xhtml:p>
            EOS
        else
            ''
        end
    end

    def convert_admonition node
        if self.is_note node and self.is_requirement node.parent
            if node.blocks?
                <<~EOS.chomp
                <note>#{node.content}</note>
                EOS
            else
                <<~EOS.chomp
                <note><xhtml:p>#{node.content}</xhtml:p></note>
                EOS
            end
        else
            ''
        end
    end

    def try_add_reference node
        a = node.attributes
        if a.key?('id') and a.key?('reftext')
            puts "MAP #{a['id']} -> #{a['reftext']}"
            @references[a['id']] = a['reftext']
        end
    end

    def convert_section node
        self.try_add_reference node
        <<~EOS.chomp
        <section title="#{node.title}" index="#{node.index}">
        <!-- #{node.attributes} -->
        #{node.content}
        </section>
        EOS
    end

    def convert_image node
        dir = node.attributes.key?('imagesdir') ? node.attributes['imagesdir'] : ""
        self.try_add_reference node
        <<~EOS.chomp
        <image
          id="#{node.attributes['id']}"
          dir="#{dir}"
          src="#{node.attributes['target']}"
          imagesdir="#{node.attributes['imagesdir']}"
          />
        <!-- #{node.attributes} -->
        <!-- #{node} -->
        EOS
    end

    def convert_table node
        content = ""
        node.rows.by_section.each do |sections|
            part_tag = "xhtml:t#{sections[0]}"
            content += "<#{part_tag}>"
            sections[1].each do |row|
                content += "<xhtml:tr>"
                row.each do |cell|
                    cell_content = cell.inner_document ? cell.inner_document.content : cell.text
                    content += "<xhtml:td colspan=\"#{cell.colspan ? cell.colspan : 1}\">#{cell_content}</xhtml:td>"
                end
                content += "</xhtml:tr>"
            end
            content += "</#{part_tag}>"
        end
        <<~EOS.chomp
        <table id="#{node.attributes['id']}">
        <xhtml:table>
        <!-- #{node.attributes} -->
        #{content}
        </xhtml:table>
        </table>
        EOS
    end

    def convert_inline_anchor node
        key = node.attributes['refid']
        if @references.key?(key)
            @references[key]
        else
            puts "KEY #{key} not found!"
            key
        end
    end

    def convert_list node
        tag = node.context == 'ulist' ? "ul": "ol"
        items = ""
        node.items.each do |item|
            items = items + "\n<xhtml:li>#{item.text}#{item.content}</xhtml:li>"
        end
        <<~EOS.chomp
        <xhtml:ol>
        #{items}
        </xhtml:ol>
        EOS
    end


    def convert node, transform=node.node_name, opts = nil
        #if node.node_name
            #puts "#{node.node_name} #{transform}"
            case node.node_name
                when 'inline_footnote', 'dlist', 'literal'
                    <<~EOS.chomp
                    <!-- #{node.node_name} -->
                    EOS
                when 'inline_quoted'
                    node.text
                when 'document'
                    self.convert_document node
                when 'section'
                    self.convert_section node
                when 'inline_anchor'
                    self.convert_inline_anchor node
                when 'paragraph'
                    self.convert_paragraph node
                when 'admonition'
                    self.convert_admonition node
                when 'olist', 'ulist'
                    self.convert_list node
                when 'image'
                    self.convert_image node
                when 'table'
                    self.convert_table node
                when 'sidebar'
                    if self.is_requirement node
                        self.convert_requirement node
                    else
                        <<~EOS.chomp
                        <#{node.node_name}>
                        <attr>#{node.attributes}</attr>
                        #{node.content}
                        </#{node.node_name}>
                        EOS
                    end
                else
                    <<~EOS.chomp
                    <!-- <#{node.node_name}> -->
                    #{node.content}
                    <!-- </#{node.node_name}> -->

                    EOS
            end
        #else
        #    puts "NO NODE NAME: #{transform}"
        #end
    end
end
